import io
import csv
import docx
from pypdf import PdfReader
from typing import Any


def extract_text(
    file_obj: Any,
    filename: str,
) -> str:
    """
    Recebe um objeto de arquivo (ex: InMemoryUploadedFile do Django) e extrai o texto bruto.
    
    Retorna:
        str: Todo o texto contido no arquivo.
    """
    extension = filename.split('.')[-1].lower()
    extracted_text = ""

    if extension in ['txt', 'md']:
        extracted_text = file_obj.read().decode('utf-8', errors='ignore')

    elif extension == 'csv':
        decoded_file = file_obj.read().decode('utf-8', errors='ignore').splitlines()
        reader = csv.reader(decoded_file)
        extracted_text = "\n".join([", ".join(row) for row in reader])

    elif extension == 'pdf':
        reader = PdfReader(file_obj)
        extracted_text = "\n".join([
            page.extract_text() for page in reader.pages if page.extract_text()
        ])

    elif extension == 'docx':
        doc = docx.Document(file_obj)
        extracted_text = "\n".join([paragraph.text for paragraph in doc.paragraphs])

    else:
        raise ValueError(f"Formato de documento não suportado: {extension}")

    # Retorna o ponteiro do arquivo para o início, caso outra parte do Django precise lê-lo novamente
    file_obj.seek(0)
    
    return extracted_text.strip()
