from lxml import etree
from pathlib import Path


from lxml import etree
from io import BytesIO


def extract_and_format(xml_content: str | bytes = None, file_path: str = None):
    """
    Extract text from TEI XML bytes/content OR file_path.

    Args:
        xml_content: Raw XML bytes or decoded string
        file_path: Alternative file path (for backward compat)
    """
    if file_path:
        # Backward compatibility
        parser = etree.XMLParser(recover=True, encoding="utf-8")
        tree = etree.parse(file_path, parser)
    elif xml_content:
        # New: from bytes/upload
        parser = etree.XMLParser(recover=True, encoding="utf-8")
        if isinstance(xml_content, str):
            tree = etree.parse(BytesIO(xml_content.encode("utf-8")), parser)
        else:
            tree = etree.parse(BytesIO(xml_content), parser)
    else:
        raise ValueError("Must provide xml_content OR file_path")

    root = tree.getroot()
    body = root.find(".//body") or root.find(".//{http://www.tei-c.org/ns/1.0}body")
    raw_text = etree.tostring(body, method="text", encoding="unicode").strip()

    ner_text, paragraphs, pages = format_for_ner(raw_text)
    return ner_text, paragraphs, pages


def format_for_ner(body_text, max_paragraphs=None):
    paragraphs = [p.strip() for p in body_text.split("\n") if p.strip()]
    cleaned_paras = []

    for para in paragraphs[: max_paragraphs or len(paragraphs)]:
        if (
            len(para) > 40
            and not para.strip().isdigit()
            and "fol." not in para.lower()
            and "exw" not in para.lower()
        ):
            words = para.split()
            if words and words[0].isdigit():
                para = " ".join(words[1:])  # Skip first word if it's a number

            para = para.replace("  --  ", " — ").replace("-- ", " — ")
            para = " ".join(para.split())

            if len(para) > 40:
                cleaned_paras.append(para)

    ner_text = "\n\n".join(cleaned_paras)

    return ner_text, cleaned_paras, []
