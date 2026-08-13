import io
from typing import Any
from PIL import Image

def prepare_image(
    file_obj: Any,
    filename: str
) -> dict:
    """
    Recebe um objeto de arquivo de imagem. Se for um formato suportado, 
    retorna os bytes. Se não for, converte para JPEG.
    
    Retorna:
        dict: Contendo o mime_type e os 'dados' (em formato de bytes) da imagem.
    """
    extension = filename.split('.')[-1].lower()
    
    supported_mime_types = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
    }
    
    if extension in supported_mime_types:
        mime_type = supported_mime_types[extension]
        image_bytes = file_obj.read()
        file_obj.seek(0)
        return {
            "mime_type": mime_type,
            "data": image_bytes
        }
        
    try:
        with Image.open(file_obj) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            output_buffer = io.BytesIO()
            img.save(output_buffer, format="JPEG")
            image_bytes = output_buffer.getvalue()
            
        # Retorna o ponteiro do arquivo para o início, caso outra parte do Django precise lê-lo novamente
        file_obj.seek(0)
        
        return {
            "mime_type": "image/jpeg",
            "data": image_bytes
        }
        
    except Exception as e:

        raise ValueError(f"Não foi possível processar ou converter a imagem '{filename}'. Erro: {str(e)}")
