from typing import Any
from .preprocessors.document_preprocessor import process_document
from .preprocessors.image_preprocessor import prepare_image


def process_upload(file_obj: Any, filename: str) -> dict:
    extension = filename.split('.')[-1].lower()
    
    image_exts = {'jpg', 'jpeg', 'png', 'webp'}
    doc_exts = {'txt', 'md', 'csv', 'pdf', 'docx'}
    
    if extension in image_exts:
        return prepare_image(file_obj, filename)
    elif extension in doc_exts:
        return process_document(file_obj, filename)
        
    raise ValueError(f"Extensão não suportada pelo sistema: {extension}")
