import json
import struct

MAX_MESSAGE = 256 * 1024
COMMANDS = {'hello','reply','status','list_runs','get_run','list_pending','get_job','save_draft',
            'update_run','settings','update_settings','export_excel','open_capture','open_folder',
            'pause','resume','import_png','pick_project','backup','restore','zotero_collections',
            'zotero_sync','zotero_key','list_papers','get_paper','update_paper','link_paper',
            'export_deliverables','prepare_capture','extract_capture','release_capture',
            'unbind_window','diagnostic_fixture','save_fixture','thumbnail','next_capture',
            'offer_refinement','get_refinement','approve_refinement','refinement_result',
            'workflow_catalog','workflow_save_package','workflow_status','workflow_start','workflow_resume','workflow_pause','workflow_stop',
            'workflow_zotero','workflow_authorize_zotero','workflow_browser','workflow_download_arm',
            'workflow_download_status','workflow_release','workflow_guard',
            'build_pdf_archive','check_project','discard_job','switch_project',
            'list_csv_imports','assign_csv_import',
            'zotero_ris_status','zotero_ris_start','screening_status','screening_approve','screening_apply','list_downloads','assign_download','offer_acm','acm_get','acm_plan','acm_progress','acm_failed','acm_part','acm_records'}


class ProtocolError(ValueError):
    pass


def validate_message(message):
    if not isinstance(message,dict) or message.get('v') != 1:
        raise ProtocolError('Desteklenmeyen ileti sürümü.')
    if not isinstance(message.get('id'),str) or not 1 <= len(message['id']) <= 100:
        raise ProtocolError('İstek kimliği eksik.')
    if message.get('type') not in COMMANDS or not isinstance(message.get('payload',{}),dict):
        raise ProtocolError('Desteklenmeyen komut.')
    return message


def _read_exact(stream, size):
    result=bytearray()
    while len(result)<size:
        part=stream.read(size-len(result))
        if not part: raise ProtocolError('İleti yarım kaldı.')
        result.extend(part)
    return bytes(result)


def read_frame(stream):
    head=stream.read(4)
    if not head:return None
    if len(head)!=4:head+=_read_exact(stream,4-len(head))
    size=struct.unpack('<I',head)[0]
    if not 0<size<=MAX_MESSAGE:raise ProtocolError('İleti boyutu sınırı aşıldı.')
    try:message=json.loads(_read_exact(stream,size).decode('utf-8'))
    except (UnicodeDecodeError,json.JSONDecodeError) as e:raise ProtocolError('Geçersiz JSON.') from e
    return validate_message(message)


def write_frame(stream,message):
    validate_message(message)
    payload=json.dumps(message,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
    if len(payload)>MAX_MESSAGE:raise ProtocolError('İleti çok büyük. Daha az kayıt seçin.')
    stream.write(struct.pack('<I',len(payload))+payload)
    stream.flush()
