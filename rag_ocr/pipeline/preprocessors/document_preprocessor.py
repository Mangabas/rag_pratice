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
        "extracted_text": None,
        "author": None,
        "subject": None,
        "keywords": None,
        "creator": None,
        "producer": None,
        "creation_date": None,
        "modification_date": None,
    }

    if extension in ['txt', 'md']:
        result["extracted_text"] = file_obj.read().decode('utf-8', errors='ignore').strip()

    elif extension == 'csv':
        decoded_file = file_obj.read().decode('utf-8', errors='ignore').splitlines()
        reader = csv.reader(decoded_file)
        result["extracted_text"] = "\n".join([", ".join(row) for row in reader]).strip()

    elif extension == 'pdf':
        reader = PdfReader(file_obj)
        result["extracted_text"] = "\n".join([
            page.extract_text() for page in reader.pages if page.extract_text()
        ]).strip()
        
        meta = reader.metadata
        if meta:
            result["author"] = meta.get('/Author')
            result["subject"] = meta.get('/Subject')
            result["keywords"] = meta.get('/Keywords')
            result["creator"] = meta.get('/Creator')
            result["producer"] = meta.get('/Producer')
            result["creation_date"] = meta.get('/CreationDate')
            result["modification_date"] = meta.get('/ModDate')

    elif extension == 'docx':
        doc = docx.Document(file_obj)
        result["extracted_text"] = "\n".join([paragraph.text for paragraph in doc.paragraphs]).strip()
        
        props = doc.core_properties
        result["author"] = props.author
        result["subject"] = props.subject
        result["keywords"] = props.keywords
        result["creation_date"] = str(props.created) if props.created else None
        result["modification_date"] = str(props.modified) if props.modified else None

    else:
        raise ValueError(f"Formato de documento não suportado: {extension}")

    # Garante que outra parte do Django possa ler o arquivo novamente
    file_obj.seek(0)
    
    return result
