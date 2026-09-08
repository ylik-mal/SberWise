"""
Модуль распознавания чеков:
1. PDF-квитанции (СберБанк, Т-Банк, Альфа, Госуслуги, чеки ОФД)
2. Фотографии чеков (QR-код ФНС + оптическое распознавание OCR)
"""

import asyncio
import io
import re
import csv
import logging
from PIL import Image
import pypdf

# Локальный NLP классификатор
from ai_module import categorize_expense, _rule_based_categorize

logger = logging.getLogger(__name__)


def parse_pdf_receipt(file_bytes: bytes) -> dict:
    """
    Извлекает данные из PDF-файла электронного чека (Сбер, банки, ОФД).
    Возвращает: {"amount": float, "description": str, "category": str, "date": str}
    """
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if not full_text.strip():
            return {"amount": 0.0, "description": "PDF Чек", "category": "🔧 Другое"}

        # Предварительно убираем время (17:37:00 или 17:37) чтобы минуты не склеивались с суммой
        text_no_time = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", "", full_text)

        # 1. Поиск суммы (с поддержкой пробелов-разделителей тысяч: 31 388 ₽)
        amount = 0.0
        amount_patterns = [
            r"(?i)(?:итого|всего|к\s+оплате|сумма(?:\s+операции|\s+платежа|\s+в\s+валюте.*?)?)[:\s]+(\d{1,3}(?:[ \xa0]\d{3})*(?:[.,]\d{2})?)\s*(?:₽|руб|rub)?",
            r"(?i)\b(\d{1,3}(?:[ \xa0]\d{3})+(?:[.,]\d{2})?)\s*(?:₽|руб|rub)\b",
            r"(?i)\b(\d{1,6}(?:[.,]\d{2})?)\s*(?:₽|руб|rub)\b",
            r"\b(\d+[.,]\d{2})\b",
        ]

        for pat in amount_patterns:
            matches = re.findall(pat, text_no_time)
            if matches:
                for m in matches:
                    clean_str = m.replace(" ", "").replace("\xa0", "").replace(",", ".")
                    try:
                        val = float(clean_str)
                        if 0 < val < 500000:
                            amount = val
                            break
                    except ValueError:
                        continue
            if amount > 0:
                break

        # 2. Поиск получателя / магазина / назначения платежа
        desc = "Чек по операции"
        desc_patterns = [
            r"(?i)(?:получатель|торговая\s+точка|место\s+расч[её]тов|магазин|организация|наименование)[:\s]+([^\n\r]+)",
            r"(?i)(?:назначение\s+платежа|описание|услуга)[:\s]+([^\n\r]+)",
            r"(?i)чек\s+по\s+операции\s+в\s+([^\n\r]+)",
        ]

        for pat in desc_patterns:
            m = re.search(pat, full_text)
            if m:
                raw_desc = m.group(1).strip()
                # Очищаем от лишних служебных символов
                raw_desc = re.sub(r"[«»\"'#*]", "", raw_desc)
                if len(raw_desc) >= 3:
                    desc = raw_desc[:40]
                    break

        # Если не нашли по паттернам, смотрим первые строки на упоминания Сбера / магазинов
        if desc == "Чек по операции":
            for line in full_text.splitlines()[:15]:
                clean_l = line.strip()
                if any(w in clean_l.lower() for w in ["сбер", "перекресток", "пятерочка", "магнит", "вкусвилл", "яндекс", "wildberries", "ozon"]):
                    desc = clean_l[:40]
                    break

        # Сначала определяем категорию по названию торговой точки/услуги
        category, _ = _rule_based_categorize(desc)
        if category == "🔧 Другое":
            category, _ = _rule_based_categorize(full_text)

        return {
            "amount": amount,
            "description": desc,
            "category": category,
        }
    except Exception as e:
        logger.error(f"Error parsing PDF receipt: {e}", exc_info=True)
        return {"amount": 0.0, "description": "Чек (ошибка чтения)", "category": "🔧 Другое"}


def parse_image_receipt(file_bytes: bytes) -> dict:
    """
    Распознаёт фото чека:
    1. Через QR-код ФНС (на всех кассовых чеках РФ)
    2. Через оптическое чтение OCR (pytesseract если доступен)
    """
    try:
        image = Image.open(io.BytesIO(file_bytes))

        # 1. Попытка прочесть кассовый QR-код (формат ФНС: t=20231015T1234&s=540.50&fn=...)
        try:
            from pyzbar.pyzbar import decode
            decoded_objs = decode(image)
            for obj in decoded_objs:
                qr_text = obj.data.decode("utf-8", errors="ignore")
                # Ищем параметр s= (сумма)
                s_match = re.search(r"\bs=([0-9]+(?:\.[0-9]{2})?)\b", qr_text)
                if s_match:
                    amount = float(s_match.group(1))
                    return {
                        "amount": amount,
                        "description": "Покупка по чеку ФНС (QR)",
                        "category": "🍞 Продукты",  # базово продукты для кассовых чеков
                    }
        except Exception as qr_err:
            logger.debug(f"QR decode error/skip: {qr_err}")

        # 2. Попытка через pytesseract (если Tesseract установлен в системе)
        try:
            import pytesseract
            ocr_text = pytesseract.image_to_string(image, lang="rus+eng")
            if ocr_text and len(ocr_text.strip()) > 10:
                # Ищем сумму в тексте
                amount_match = re.search(r"(?i)(?:итог|итого|к\s+оплате|всего|сумма)[:\s]*([0-9\s]+[.,][0-9]{2})", ocr_text)
                amount = 0.0
                if amount_match:
                    raw_s = amount_match.group(1).replace(" ", "").replace(",", ".")
                    amount = float(raw_s)

                category, desc = _rule_based_categorize(ocr_text[:300])
                if amount > 0:
                    return {
                        "amount": amount,
                        "description": desc or "Покупка по чеку",
                        "category": category,
                    }
        except Exception as ocr_err:
            logger.debug(f"OCR not available or failed: {ocr_err}")

        # Если ничего не удалось извлечь автоматически
        return {
            "amount": 0.0,
            "description": "Фото чека",
            "category": "🍞 Продукты",
        }

    except Exception as e:
        logger.error(f"Error parsing image receipt: {e}", exc_info=True)
        return {"amount": 0.0, "description": "Фото чека", "category": "🔧 Другое"}


# ─── Расширенный парсинг документов (PDF/CSV) и позиций чеков ───

def parse_document_receipt(file_bytes: bytes, filename: str, room_members: list[dict]) -> dict:
    """
    Парсит PDF или CSV файл (например: Ozon_Travel_Booking_883.pdf, квитанции, выписки).
    Возвращает структуру ParsedExpenseDraft с позициями и участниками.
    """
    all_member_ids = [m["id"] for m in room_members]
    fname_lower = filename.lower()
    if not file_bytes:
        return {"error": "empty_file", "message": "Файл пуст."}

    if fname_lower.endswith(".csv"):
        try:
            full_text = file_bytes.decode("utf-8-sig", errors="strict")
            reader = csv.reader(io.StringIO(full_text))
            items = []
            for row in reader:
                if not row:
                    continue
                name = (row[0] or "Позиция").strip()
                amounts = []
                for cell in row[1:]:
                    raw = re.sub(r"[^\d.,]", "", cell).replace(",", ".")
                    try:
                        value = float(raw)
                        if value > 0:
                            amounts.append(value)
                    except ValueError:
                        pass
                if amounts:
                    amount = amounts[-1]
                    cat, _ = _rule_based_categorize(name)
                    items.append({"name": name, "quantity": 1.0, "unit_price": amount, "total_amount": amount, "category": cat, "participants": all_member_ids})
            if not items:
                return {"error": "no_data", "message": "В CSV не найдены строки с суммами."}
            total = round(sum(i["total_amount"] for i in items), 2)
            return {"title": f"Импорт CSV ({filename})", "merchant": "Документ CSV", "currency": "RUB", "total_amount": total, "confidence": 0.85, "source_type": "csv", "items": items}
        except UnicodeDecodeError:
            return {"error": "invalid_csv", "message": "CSV должен быть в UTF-8."}

    if not fname_lower.endswith(".pdf"):
        return {"error": "unsupported_file", "message": "Поддерживаются только PDF и CSV."}
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        full_text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return {"error": "invalid_pdf", "message": "Не удалось открыть PDF. Проверьте, что файл не повреждён или не защищён паролем."}
    if not full_text:
        return {"error": "no_text", "message": "В PDF нет текстового слоя. Для сканированного PDF загрузите изображение чека."}

    # Extract real amounts from the document; never invent a fallback total.
    money = re.compile(r"(\d{1,3}(?:[ \xa0]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s*(?:₽|руб(?:\.?|лей|ля)?|RUB)", re.IGNORECASE)
    amounts = [float(m.group(1).replace(" ", "").replace("\xa0", "").replace(",", ".")) for m in money.finditer(full_text)]
    if not amounts:
        return {"error": "no_amount", "message": "В PDF не найдена сумма в рублях."}
    total = amounts[-1]
    for label in ("итого", "всего", "к оплате", "total", "amount"):
        match = re.search(rf"{label}[^\d]*(\d[\d \xa0]*(?:[.,]\d{{1,2}})?)", full_text, re.IGNORECASE)
        if match:
            total = float(match.group(1).replace(" ", "").replace("\xa0", "").replace(",", "."))
            break

    lines = [re.sub(r"\s+", " ", line).strip() for line in full_text.splitlines() if line.strip()]
    merchant = next((line[:80] for line in lines[:10] if not re.search(r"\d{3,}", line) and len(line) >= 3), "Документ")
    date_match = re.search(r"\b(\d{2}[./-]\d{2}[./-]\d{4}|\d{4}[./-]\d{2}[./-]\d{2})\b", full_text)
    items = []
    for line in lines:
        match = money.search(line)
        if not match:
            continue
        amount = float(match.group(1).replace(" ", "").replace("\xa0", "").replace(",", "."))
        name = line[:match.start()].strip(" -—:;\t") or merchant
        if len(name) < 2 or re.search(r"(?i)итого|всего|к оплате|total|amount", name):
            continue
        cat, _ = _rule_based_categorize(name)
        items.append({"name": name[:120], "quantity": 1.0, "unit_price": amount, "total_amount": amount, "category": cat, "participants": all_member_ids})
    if not items:
        cat, _ = _rule_based_categorize(merchant)
        items = [{"name": merchant, "quantity": 1.0, "unit_price": total, "total_amount": total, "category": cat, "participants": all_member_ids}]
    return {"title": merchant, "merchant": merchant, "date": date_match.group(1) if date_match else None, "currency": "RUB", "total_amount": round(total, 2), "confidence": 0.80, "source_type": "pdf", "items": items, "extracted_text": full_text[:12000]}


async def parse_image_receipt_items(file_bytes: bytes, room_members: list[dict]) -> dict:
    """
    Распознавание позиций из реального фото чека:
    1. PIL-предобработка: EXIF auto-rotate, масштабирование до 2000px
    2. Сканирование кассового QR-кода ФНС через pyzbar
    3. Оптическое распознавание и структурирование через OpenAI GPT-4o-mini Vision
    4. Автоматическая категоризация и сверка sum(items) vs receipt.total
    5. Fallback на локальный Tesseract/QR при отсутствии связи
    """
    import base64
    import json
    from PIL import ImageOps
    from ai_module import openai_client

    all_member_ids = [m["id"] for m in room_members]
    if not file_bytes:
        return {
            "error": "empty_ocr",
            "message": "Файл изображения чека пуст."
        }

    # 1. Предобработка изображения через PIL
    try:
        image = Image.open(io.BytesIO(file_bytes))
        image = ImageOps.exif_transpose(image)
        if image.mode != "RGB":
            image = image.convert("RGB")
        # Ограничиваем размер до 2000px для оптимизации передачи и скорости OCR
        max_dim = max(image.size)
        if max_dim > 2000:
            image.thumbnail((2000, 2000), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=85)
        processed_bytes = buf.getvalue()
        logger.info("RECEIPT_IMAGE_READY width=%s height=%s input_bytes=%s output_bytes=%s", image.width, image.height, len(file_bytes), len(processed_bytes))
    except Exception as img_err:
        logger.error(f"Image preprocessing failed: {img_err}", exc_info=True)
        return {
            "error": "invalid_image",
            "message": "Не удалось прочитать изображение. Убедитесь, что это файл формата JPG, PNG или WebP."
        }

    # 2. Попытка извлечь QR-код ФНС
    qr_sum = None
    try:
        from pyzbar.pyzbar import decode
        decoded_objs = decode(image)
        for obj in decoded_objs:
            qr_text = obj.data.decode("utf-8", errors="ignore")
            s_match = re.search(r"\bs=([0-9]+(?:\.[0-9]{2})?)\b", qr_text)
            if s_match:
                qr_sum = float(s_match.group(1))
                logger.info(f"FNS QR code found with sum={qr_sum}₽")
                break
    except Exception as qr_err:
        logger.debug(f"pyzbar QR decode skipped: {qr_err}")

    # 3. Вызов OpenAI GPT-4o-mini Vision (если подключен)
    if openai_client:
        try:
            b64_img = base64.b64encode(processed_bytes).decode("utf-8")
            system_prompt = (
                "Ты — экспертная OCR-система финансового сервиса СберСплит для распознавания чеков. "
                "Проанализируй фото кассового или товарного чека и извлеки информацию.\n"
                "Верни СТРОГО валидный JSON-объект следующей структуры:\n"
                "{\n"
                '  "merchant": "Название магазина/заведения",\n'
                '  "date": "Дата покупки (если есть)",\n'
                '  "total_amount": 0.0,\n'
                '  "currency": "RUB",\n'
                '  "confidence": 0.95,\n'
                '  "items": [\n'
                '    {\n'
                '      "name": "Название товара",\n'
                '      "quantity": 1.0,\n'
                '      "unit_price": 0.0,\n'
                '      "total_amount": 0.0,\n'
                '      "category": "Категория"\n'
                '    }\n'
                '  ]\n'
                "}\n"
                "Если на фото нет чека или текст нечитаем, верни JSON: {\"error\": \"unreadable\"}.\n"
                "Отвечай ТОЛЬКО JSON без пояснений и без markdown кавычек."
            )

            prompt_text = "Распознай этот чек и верни JSON с позициями, ценами и итогом."
            if qr_sum:
                prompt_text += f" (Подсказка: на кассовом QR-коде ФНС зафиксирована точная сумма: {qr_sum} ₽)."

            response = await asyncio.wait_for(
                openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_text},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{b64_img}",
                                        "detail": "high"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=1200,
                    temperature=0.1
                ),
                timeout=35,
            )

            raw_resp = response.choices[0].message.content.strip()
            # Очистка от markdown code blocks если они вернулись
            if raw_resp.startswith("```"):
                raw_resp = re.sub(r"^```(?:json)?\s*", "", raw_resp)
                raw_resp = re.sub(r"\s*```$", "", raw_resp)

            parsed = json.loads(raw_resp)
            if not parsed.get("error") and (parsed.get("items") or parsed.get("total_amount")):
                merchant = (parsed.get("merchant") or "Чек покупки").strip()
                raw_items = parsed.get("items") or []
                total_amount = float(parsed.get("total_amount") or qr_sum or 0.0)

                items = []
                for it in raw_items:
                    it_name = str(it.get("name") or "Товар").strip()
                    try:
                        it_qty = float(it.get("quantity") or 1.0)
                    except (ValueError, TypeError):
                        it_qty = 1.0
                    try:
                        it_tot = float(it.get("total_amount") or it.get("unit_price") or 0.0)
                    except (ValueError, TypeError):
                        it_tot = 0.0
                    try:
                        it_price = float(it.get("unit_price") or (it_tot / it_qty if it_qty else it_tot))
                    except (ValueError, TypeError):
                        it_price = it_tot

                    it_cat = it.get("category")
                    if not it_cat or it_cat == "🔧 Другое":
                        it_cat, _ = _rule_based_categorize(it_name)

                    items.append({
                        "name": it_name,
                        "quantity": round(it_qty, 2),
                        "unit_price": round(it_price, 2),
                        "total_amount": round(it_tot, 2),
                        "category": it_cat,
                        "participants": list(all_member_ids),
                    })

                items_sum = sum(i["total_amount"] for i in items)
                if total_amount <= 0.0 and items_sum > 0:
                    total_amount = items_sum

                # Сверка сумм
                warning = None
                if items and abs(items_sum - total_amount) > 1.0:
                    warning = f"Сумма позиций ({round(items_sum, 2)} ₽) отличается от итога чека ({round(total_amount, 2)} ₽). Пожалуйста, проверьте позиции."

                return {
                    "title": merchant,
                    "merchant": merchant,
                    "currency": "RUB",
                    "total_amount": round(total_amount, 2),
                    "confidence": float(parsed.get("confidence") or 0.95),
                    "source_type": "receipt_photo",
                    "items": items,
                    "warning": warning,
                    "qr_verified": bool(qr_sum and abs(qr_sum - total_amount) < 0.1)
                }
        except asyncio.TimeoutError:
            logger.warning("RECEIPT_OCR_PROVIDER_TIMEOUT")
        except Exception as ai_err:
            logger.error(f"OpenAI Vision OCR failed: {ai_err}", exc_info=True)

    # 4. Локальный fallback (Tesseract / Regex / QR)
    lines_text = ""
    try:
        import pytesseract
        lines_text = pytesseract.image_to_string(image, lang="rus+eng")
    except Exception:
        pass

    items = []
    total = qr_sum or 0.0
    for line in lines_text.splitlines():
        line = line.strip()
        amt_match = re.search(r"(\d+[.,]\d{2})", line)
        if amt_match:
            try:
                amt = float(amt_match.group(1).replace(",", "."))
                name = line[:amt_match.start()].strip(" -—:*\t")
                if len(name) >= 3 and amt > 0:
                    cat, _ = _rule_based_categorize(name)
                    items.append({
                        "name": name,
                        "quantity": 1.0,
                        "unit_price": amt,
                        "total_amount": amt,
                        "category": cat,
                        "participants": list(all_member_ids),
                    })
                    if not qr_sum:
                        total += amt
            except ValueError:
                continue

    if qr_sum and not items:
        items = [{
            "name": "Покупка по чеку ФНС",
            "quantity": 1.0,
            "unit_price": qr_sum,
            "total_amount": qr_sum,
            "category": "🍞 Продукты",
            "participants": list(all_member_ids),
        }]
        total = qr_sum

    if not items and total <= 0:
        return {
            "error": "empty_ocr",
            "message": "Не удалось распознать чек. Попробуйте сделать фото ближе и при хорошем освещении или загрузите другое изображение."
        }

    items_sum = sum(i["total_amount"] for i in items)
    warning = None
    if items and abs(items_sum - total) > 1.0:
        warning = f"Сумма позиций ({round(items_sum, 2)} ₽) отличается от итога чека ({round(total, 2)} ₽). Проверьте данные."

    return {
        "title": "Чек покупки",
        "merchant": "Магазин (по чеку)",
        "currency": "RUB",
        "total_amount": round(total, 2),
        "confidence": 0.85 if qr_sum else 0.70,
        "source_type": "receipt_photo",
        "items": items,
        "warning": warning,
        "qr_verified": bool(qr_sum)
    }
