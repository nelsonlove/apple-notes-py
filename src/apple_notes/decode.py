"""Gzip + protobuf decoding of Apple Notes content blobs."""

import zlib

from .proto.notestore_pb2 import NoteStoreProto


def decode_note_content(content: bytes | None) -> str:
    """Decode a ZICNOTEDATA.ZDATA blob into plain text.

    The blob is gzip-compressed protobuf. The message hierarchy is:
    NoteStoreProto → Document → Note → note_text
    """
    if not content:
        return ""

    if not content.startswith(b"\x1f\x8b"):
        return ""

    decompressed = zlib.decompress(content, 16 + zlib.MAX_WBITS)

    note_store = NoteStoreProto()
    note_store.ParseFromString(decompressed)

    if note_store.document and note_store.document.note:
        return note_store.document.note.note_text or ""

    return ""
