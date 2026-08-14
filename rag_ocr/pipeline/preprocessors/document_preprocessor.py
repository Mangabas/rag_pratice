import csv
import docx
from pypdf import PdfReader
from typing import Any

def process_document(file_obj: Any, filename: str) -> dict:
    """
    Recebe um objeto de arquivo (ex: InMemoryUploadedFile do Django) e o nome do arquivo para extrair o texto bruto e os seus metadados.

    Retorna:
        dict: Dicionário estruturado contendo o texto extraído, extensão do arquivo e metadados.
    """
    
    extension = filename.split('.')[-1].lower()

    result = {
        "file_name": filename,
        "file_extension": extension,
        "extracted_text": "",
        "page_count": None,
        "pages_data": [],
        "subject": None,
        "keywords": None,
        "creator": None,
        "producer": None,
        "creation_date": None,
        "modification_date": None,
    }

    if extension in ['txt', 'md']:
        text = file_obj.read().decode('utf-8', errors='ignore').strip()
        result["extracted_text"] = text
        result["pages_data"] = [{"text": text, "page_number": 1}]
        result["page_count"] = 1

    elif extension == 'csv':
        decoded_file = file_obj.read().decode('utf-8', errors='ignore').splitlines()
        reader = csv.reader(decoded_file)
        text = "\n".join([", ".join(row) for row in reader]).strip()
        result["extracted_text"] = text
        result["pages_data"] = [{"text": text, "page_number": 1}]
        result["page_count"] = 1

    elif extension == 'pdf':
        reader = PdfReader(file_obj)
        result["page_count"] = len(reader.pages)
        
        full_text = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                full_text.append(page_text)
                result["pages_data"].append({
                    "text": page_text,
                    "page_number": i + 1
                })
        result["extracted_text"] = "\n".join(full_text).strip()
        
        meta = reader.metadata
        if meta:
            result["subject"] = meta.get('/Subject')
            result["keywords"] = meta.get('/Keywords')
            result["creator"] = meta.get('/Creator')
            result["producer"] = meta.get('/Producer')
            result["creation_date"] = meta.get('/CreationDate')
            result["modification_date"] = meta.get('/ModDate')

    elif extension == 'docx':
        doc = docx.Document(file_obj)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs]).strip()
        result["extracted_text"] = text
        result["pages_data"] = [{"text": text, "page_number": 1}]
        result["page_count"] = 1
        
        props = doc.core_properties
        result["subject"] = props.subject
        result["keywords"] = props.keywords
        result["creation_date"] = str(props.created) if props.created else None
        result["modification_date"] = str(props.modified) if props.modified else None

    else:
        raise ValueError(f"Formato de documento não suportado: {extension}")

    file_obj.seek(0)
    
    return result
