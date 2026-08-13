import io
import base64
from typing import Any
from PIL import Image, ExifTags

def get_exif_data(img: Image.Image) -> dict:
    """
    Recebe um objeto de imagem da biblioteca Pillow para extrair os metadados originais embutidos no formato EXIF.

    Retorna:
        dict: Dicionário contendo os dados de localização geográfica e as datas de criação e modificação.
    """

    exif_data = {"geo_data": None, "creation_date": None, "modification_date": None}
    exif = img.getexif()
    
    if not exif:
        return exif_data

    for tag_id, value in exif.items():
        tag = ExifTags.TAGS.get(tag_id, tag_id)
        if tag == "DateTimeOriginal":
            exif_data["creation_date"] = value
        elif tag == "DateTime":
            exif_data["modification_date"] = value
            
    gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
    if gps_ifd:
        exif_data["geo_data"] = {ExifTags.GPSTAGS.get(key, key): val for key, val in gps_ifd.items()}
        
    return exif_data


def prepare_image(file_obj: Any, filename: str) -> dict:
    """
    Recebe um objeto de arquivo de imagem e o nome do arquivo, extrai os metadados EXIF e converte a imagem em bytes padronizados.

    Retorna:
        dict: Dicionário contendo a estrutura base dos dados da imagem, metadados extraídos e os bytes preparados para envio.
    """

    extension = filename.split('.')[-1].lower()
    
    result = {
        "file_name": filename,
        "file_orig_extension": extension,
        "extracted_text": None,
        "img_base64": None,
        "extracted_objects": [],
        "description": None,
        "image_views": 0,
        "geo_data": None,
        "creation_date": None,
        "modification_date": None,
        "_llm_mime_type": "image/jpeg", 
        "_llm_bytes": b""
    }

    try:
        with Image.open(file_obj) as img:
            exif_info = get_exif_data(img)
            result.update(exif_info)

            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            output_buffer = io.BytesIO()
            img.save(output_buffer, format="JPEG")
            
            img_bytes = output_buffer.getvalue()
            result["_llm_bytes"] = img_bytes
            result["img_base64"] = base64.b64encode(img_bytes).decode('utf-8')
            
    except Exception as e:
        raise ValueError(f"Não foi possível processar a imagem '{filename}'. Erro: {str(e)}")

    # Garante que outra parte do Django possa ler o arquivo novamente
    file_obj.seek(0)
    
    return result