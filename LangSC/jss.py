"""JSS (JSON Structure Search) class wrapping jsslib.dll."""

import os
import platform
import json
from ctypes import *

from ._utils import (
    detect_file_encoding, get_idx_info, get_jss_file_info, is_same,
    get_jss_files, write_idx_log,
)

OS = platform.system()
if OS == "Windows":
    import win32api


class JSS:
    def __init__(self, dataPath, log_level=0, log_filename=''):
        dataPath = dataPath.replace("\\", "/")
        if dataPath[-1] == "/":
            dataPath = dataPath[:-1]
        if dataPath.find("./") != 0:
            dataPath = "./" + dataPath
        if dataPath.find(".") != 0:
            dataPath = "." + dataPath

        dll_name_jss = ''

        if OS == "Windows":
            dll_name_jss = 'jsslib.dll'
        elif OS == "Linux":
            dll_name_jss = 'libjsslib.so'
        else:
            dll_name_jss = 'libjsslib.dylib'

        self.g_IdxLog = "IdxLog_JSS.txt"
        self.log_level = log_level
        self.log_filename = log_filename
        self.buf_max_size = 1024 * 1024 * 10
        self.RetBuff = create_string_buffer(''.encode(), self.buf_max_size)
        self.is_init = False
        self.dataPath = dataPath
        self.handles = {}
        self.dll_close = None
        self.library_jss = None
        dll_file_jss = os.path.join(os.path.dirname(os.path.abspath(__file__)), dll_name_jss)
        self.library_jss = cdll.LoadLibrary(dll_file_jss)

        if OS == "Windows":
            self.dll_close = win32api.FreeLibrary
        elif OS == "Linux":
            try:
                stdlib = CDLL("")
            except OSError:
                stdlib = CDLL("libc.so")
            self.dll_close = stdlib.dlclose
            self.dll_close.argtypes = [c_void_p]
        else:
            self.dll_close = None

        self._init_jss_data(dataPath)

    def __del__(self):
        if self.handles:
            self.Terminate()
        if self.dll_close is not None and self.library_jss is not None:
            self.dll_close(self.library_jss._handle)

    def _init_jss_data(self, path):
        """Auto-detect: if IdxLog_JSS.txt exists, load indexed tables;
        otherwise treat as raw JSON data, index first, then load."""
        idxed_file2time = {}
        to_idx_file2time = {}
        jss_files = []

        ret = get_idx_info(path, self.g_IdxLog, idxed_file2time)
        self.dataPath = path
        if len(idxed_file2time) > 0 or ret:
            self._load_all_tables(path)
            return True

        get_jss_file_info(path, to_idx_file2time)
        if len(to_idx_file2time) == 0:
            return True

        path_idx = path + "Idx"
        self.dataPath = path_idx
        get_idx_info(path_idx, self.g_IdxLog, idxed_file2time)
        get_jss_files(path, idxed_file2time, jss_files)

        if is_same(to_idx_file2time, idxed_file2time):
            self._load_all_tables(path_idx)
            return True

        if not os.path.exists(path_idx):
            os.makedirs(path_idx)

        for json_file in jss_files:
            name = os.path.splitext(os.path.basename(json_file))[0]
            cfg_file = os.path.join(path, "cfg_{}.txt".format(name))
            if not os.path.isfile(cfg_file):
                cfg_file = self._generate_cfg(json_file)
            out_dir = os.path.join(path_idx, name)
            print("Indexing JSS", json_file)
            self._create_table(cfg_file, json_file, out_dir)
            write_idx_log(path_idx, json_file, self.g_IdxLog)

        self._load_all_tables(path_idx)
        return True

    def _generate_cfg(self, json_file):
        """Auto-generate a cfg_*.txt by reading the first record of a JSON/JSONL file."""
        name = os.path.splitext(os.path.basename(json_file))[0]
        encoding = detect_file_encoding(json_file)

        # Read first record
        if json_file.endswith('.jsonl'):
            record_format = "jsonl"
            with open(json_file, 'r', encoding=encoding) as f:
                record = json.loads(f.readline().strip())
        else:
            record_format = "json"
            with open(json_file, 'r', encoding=encoding) as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                record = data[0]
            elif isinstance(data, dict):
                record = data
            else:
                record = {}

        # Build content: array fields get "[]" suffix
        content = {}
        for key, value in record.items():
            if isinstance(value, list):
                content[key + "[]"] = key + "[]"
            else:
                content[key] = key

        # Build index
        number_fields = []
        kv_fields = []
        for key, value in record.items():
            if key == "id" and isinstance(value, (int, float)):
                number_fields.append(key)
            elif isinstance(value, str):
                kv_fields.append(key)

        cfg = {
            "table_name": name,
            "record_format": record_format,
            "content": content,
            "index": {
                "number": number_fields,
                "kv": kv_fields,
                "affix": [],
                "bm25": []
            }
        }

        cfg_path = os.path.join(os.path.dirname(json_file), "cfg_{}.txt".format(name))
        with open(cfg_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        print("Generated cfg", cfg_path)
        return cfg_path

    def _load_all_tables(self, idx_path):
        """Load all indexed table subdirectories."""
        for name in sorted(os.listdir(idx_path)):
            sub = os.path.join(idx_path, name)
            if os.path.isdir(sub):
                self._load_table(sub, name)

    def _create_table(self, cfg_filename, dat_pathname, out_pathname, seg_filename=''):
        if os.path.isfile(seg_filename):
            seg_fullname = os.path.abspath(seg_filename)
        else:
            seg_fullname = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'base.lex')

        self.library_jss.JL_CreateTable.restype = c_int
        self.library_jss.JL_CreateTable.argtypes = [c_char_p, c_char_p, c_char_p, c_char_p, c_int, c_char_p]
        ret = self.library_jss.JL_CreateTable(cfg_filename.encode(), seg_fullname.encode(), dat_pathname.encode(), out_pathname.encode(), self.log_level, self.log_filename.encode())
        return ret

    def _load_table(self, filename, name=""):
        self.library_jss.JL_Initialize.restype = c_void_p
        self.library_jss.JL_Initialize.argtypes = [c_char_p, c_int, c_char_p]
        handle = self.library_jss.JL_Initialize(filename.encode(), self.log_level, self.log_filename.encode())
        if not name:
            name = os.path.basename(filename)
        self.handles[name] = handle
        self.is_init = True
        return handle

    def Run(self, sql_statement, table=""):
        if not self.is_init:
            return []
        if table and table in self.handles:
            handle = self.handles[table]
        else:
            handle = next(iter(self.handles.values()))
        self.library_jss.JL_RunSql.restype = c_int
        self.library_jss.JL_RunSql.argtypes = [c_void_p, c_char_p, c_char_p, c_int]
        str_len = self.library_jss.JL_RunSql(handle, sql_statement.encode(), self.RetBuff, self.buf_max_size)
        ret = string_at(self.RetBuff, str_len)
        json_data = json.loads(ret.decode())
        return json_data['results']

    def Terminate(self):
        if self.is_init:
            self.library_jss.JL_Terminate.argtypes = [c_void_p]
            for handle in self.handles.values():
                self.library_jss.JL_Terminate(handle)
            self.handles = {}
            self.is_init = False
