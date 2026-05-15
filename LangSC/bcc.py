"""BCC (BCC Corpus) class wrapping bcclib.dll only."""

import json
import os
import re
import platform
import threading
from ctypes import *

from ._utils import (
    get_idx_info, get_file_info, is_same, get_bcc_files,
    write_idx_log, is_file_list, is_raw, process_file,
    file2corpus, corpus,
)

OS = platform.system()
if OS == "Windows":
    import win32api

IsBCCInit = 0
lock = threading.Lock()


class BCC:
    def __init__(self, dataPath="./data"):
        dataPath = dataPath.replace("\\", "/")
        if dataPath[-1] == "/":
            dataPath = dataPath[:-1]
        if dataPath.find("./") != 0:
            dataPath = "./" + dataPath
        if dataPath.find(".") != 0:
            dataPath = "." + dataPath

        dll_name_bcc = ''
        self.g_IdxLog = "IdxLog_BCC.txt"
        if OS == "Windows":
            dll_name_bcc = 'bcclib.dll'
        elif OS == "Linux":
            dll_name_bcc = 'libbcclib.so'
        else:
            dll_name_bcc = 'libbcclib.dylib'

        self.buf_max_size = 1024 * 10000
        dll_file_bcc = os.path.join(os.path.dirname(os.path.abspath(__file__)), dll_name_bcc)
        cfg_file_bcc = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'BCCconfig.txt')
        cfg_file_parser = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Parser.lua')

        self.library_bcc = cdll.LoadLibrary(dll_file_bcc)

        self.ParserBCC = cfg_file_parser
        self.ConfigBCC = cfg_file_bcc
        self.dataPath = dataPath
        self.RetBuff = create_string_buffer(''.encode(), self.buf_max_size)

        if OS == "Windows":
            self.dll_close = win32api.FreeLibrary
        elif OS == "Linux":
            try:
                stdlib = CDLL("")
            except OSError:
                stdlib = CDLL("libc.so")
            self.dll_close = stdlib.dlclose
            self.dll_close.argtypes = [c_void_p]

        self._gpf = None
        self._init_bcc_data(dataPath)

    def _get_gpf(self):
        """Lazily create a GPF instance for segmentation and POS tagging."""
        if self._gpf is None:
            from .gpf import GPF
            self._gpf = GPF()
        return self._gpf

    def __del__(self):
        return

    def _init_bcc_data(self, path):
        """Initialize BCC data by scanning and indexing BCC corpus files.

        Path resolution:
        1) path itself is index dir → use directly
        2) path+"Idx" is index dir → use that
        3) Otherwise, collect files under path (recursive), build index in path+"Idx"
        4) Set dataPath to path+"Idx" for querying
        """
        # 1) path 本身就是索引目录
        idxed_file2time = {}
        ret = get_idx_info(path, self.g_IdxLog, idxed_file2time)
        if len(idxed_file2time) > 0 or ret:
            self.dataPath = path
            return True

        # 2) path+"Idx" 是索引目录
        path_idx = path + "Idx"
        idxed_file2time = {}
        ret = get_idx_info(path_idx, self.g_IdxLog, idxed_file2time)
        if len(idxed_file2time) > 0 or ret:
            self.dataPath = path_idx
            return True

        # 3) 回到原路径，递归收集所有文件，建索引到 path+"Idx"
        to_idx_file2time = {}
        get_file_info(path, to_idx_file2time)
        if len(to_idx_file2time) == 0:
            self.dataPath = path
            return True

        bcc_files = []
        get_bcc_files(path, idxed_file2time, bcc_files)

        if len(bcc_files) > 0:
            self.dataPath = path_idx
            print("BCC: indexing {} file(s) ...".format(len(bcc_files)))
            has_raw = any(is_raw(f) for f in bcc_files)
            if has_raw:
                self.IndexBCC(bcc_files, Structure="Segment")
            else:
                self.IndexBCC(bcc_files)
            for f in bcc_files:
                write_idx_log(path_idx, f, self.g_IdxLog)
            print("BCC: indexing done.")

        # 4) 设置 dataPath 为索引目录
        self.dataPath = path_idx
        return True

    def CallBCC(self, query):
        """Execute a BCC query."""
        global IsBCCInit
        lock.acquire()
        if IsBCCInit == 0:
            self.library_bcc.BCC_Init.argtypes = [c_char_p]
            self.library_bcc.BCC_Init.restype = c_int
            IsBCCInit = self.library_bcc.BCC_Init(self.dataPath.encode('gbk', errors='strict'))
        lock.release()

        if IsBCCInit == 0 and query.find("Lua") == -1:
            return json.loads("{}")
        self.library_bcc.BCC_RunBCC.argtypes = [c_char_p, c_char_p, c_char_p, c_char_p]
        self.library_bcc.BCC_RunBCC.restype = c_int
        str_len = self.library_bcc.BCC_RunBCC(self.ParserBCC.encode(), self.dataPath.encode('gbk', errors='strict'), query.encode(), self.RetBuff)
        ret = string_at(self.RetBuff, str_len)
        return ret.decode()

    def Run(self, Query, **Others):
        """Run a BCC query with keyword arguments."""
        Param = []
        self.GetBCCQueryInfo(Others, Query, Param)
        ret = self.CallBCC(Param[0])
        command = Others.get("Command", Others.get("Output", "Freq"))
        if command == "Context":
            ret = self._clean_source_id(ret)
        elif command == "Freq":
            ret = self._clean_freq_source(ret)
        return ret

    def _clean_freq_source(self, ret):
        """Format Source field in Freq results for readability.

        Replaces \\ with / in paths, and puts each source:count on its own line.
        """
        try:
            data = json.loads(ret)
            if isinstance(data, dict) and "Source" in data:
                source = data["Source"]
                if isinstance(source, dict):
                    for key in source:
                        val = source[key]
                        if isinstance(val, str):
                            val = val.replace("\\", "/")
                            parts = val.split(" ")
                            source[key] = " ".join(parts)
            ret = json.dumps(data, ensure_ascii=False, indent=2)
            # Make newlines in Source values display as actual line breaks
            return ret
        except (json.JSONDecodeError, TypeError):
            return ret

    def _clean_source_id(self, ret):
        """Remove SourceID fields from Context results."""
        try:
            data = json.loads(ret)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        item.pop("SourceID", None)
            elif isinstance(data, dict):
                data.pop("SourceID", None)
                for v in data.values():
                    if isinstance(v, list):
                        for item in v:
                            if isinstance(item, dict):
                                item.pop("SourceID", None)
            ret = json.dumps(data, ensure_ascii=False, indent=2)
            return ret.replace("\\\\", "/")
        except (json.JSONDecodeError, TypeError):
            return ret

    def AddBCCKV(self, Key, Val):
        """Add a key-value pair to the BCC context."""
        Values = re.split(r"[ ;,\t]", Val)
        Val = ";".join(Values)
        Query = "AddKV({},{})".format(Key, Val)
        return self.CallBCC(Query)

    def GetBCCKV(self, Key=""):
        """Get a BCC key-value."""
        if Key == "":
            Query = "GetKV()"
        else:
            Query = "GetKV({})".format(Key)
        return self.CallBCC(Query)

    def GetBCCKVs(self, Key=""):
        """Get BCC key-values."""
        if Key == "":
            Query = "GetKV()"
        else:
            Query = "GetKV({})".format(Key)
        return self.CallBCC(Query)

    def ClearBCCKV(self, Key=""):
        """Clear BCC key-values."""
        Query = "ClearKV()"
        return self.CallBCC(Query)

    def IndexBCC(self, filelistname, **Others):
        """Index BCC corpus files."""
        ret = 0
        if not os.path.exists(self.dataPath):
            os.mkdir(os.path.abspath(self.dataPath))
        Param = []
        self.GetIndexBCCInfo(Others, Param)
        self.library_bcc.BCC_IndexBCC.argtypes = [c_char_p, c_char_p, c_char_p]
        self.library_bcc.BCC_IndexBCC.restype = c_int
        filelist = os.path.join(self.dataPath, "indexlist.tmp")
        if isinstance(filelistname, str):
            if os.path.isdir(filelistname):
                filelist_names = []
                corpus(filelistname, filelist_names)
                with open(filelist, "w") as out:
                    for f in filelist_names:
                        print(f, file=out)
            else:
                if is_file_list(filelistname):
                    filelist = filelistname
                else:
                    with open(filelist, "w") as out:
                        print(filelistname, file=out)
        else:
            with open(filelist, "w") as out:
                for f in filelistname:
                    print(f, file=out)
        filelist_ex = os.path.join(self.dataPath, "indexlistEx.tmp")
        gpf = self._get_gpf() if Param[0] == "Segment" else None
        file2corpus(filelist, filelist_ex, self.dataPath, Param[0], gpf=gpf)
        ret = self.library_bcc.BCC_IndexBCC(self.ConfigBCC.encode(), filelist_ex.encode('gbk', errors='strict'), self.dataPath.encode('gbk', errors='strict'))
        os.remove(filelist_ex)
        if filelist.find("indexlist.tmp") != -1:
            os.remove(filelist)
        return ret

    def GetIndexBCCInfo(self, Others, Param):
        """Parse IndexBCC parameters."""
        Command = "HZ"
        if "Structure" in Others:
            Command = Others["Structure"]
        Param.append(Command)

    def GetBCCQueryInfo(self, Others, Query, Param):
        """Parse BCC query parameters."""
        Command = ""
        if Query.find("\n") != -1:
            BCCQuery = Query
            Param.append(BCCQuery)
            return

        else:
            Command = "Freq"

        Number = 100
        Target = "$Q"
        WinSize = 20
        Print = ""
        PageNo = 0
        Speedup = 1
        ContextNum = 0

        if "Command" in Others:
            Command = Others["Command"]
        if "Output" in Others:
            Command = Others["Output"]
        if "Number" in Others:
            Number = Others["Number"]
        if "Target" in Others:
            Target = Others["Target"]
        if "WinSize" in Others:
            WinSize = Others["WinSize"]
        if "Print" in Others:
            Print = Others["Print"]
        if "PageNo" in Others:
            PageNo = Others["PageNo"]
        if "Speedup" in Others:
            Speedup = Others["Speedup"]
        if "ContextNum" in Others:
            ContextNum = Others["ContextNum"]

        Operation = ""
        if Command == "Context":
            Operation = "Context({},{},{})".format(WinSize, PageNo, Number)
        elif Command == "Freq":
            Operation = 'Freq({},{},{})'.format(Number, Target, ContextNum)
        elif Command == "Count":
            Operation = "Count()".format()
        else:
            Operation = "{}".format(Command)
        if not re.search(r"[\{\}]", Query):
            Query += "{}"

        BCCQuery = ""
        if Query.find(" AND ") != -1:
            BCCQuery = re.sub(r" AND ", Operation + " AND ", Query)
        elif Query.find(" NOT ") != -1:
            BCCQuery = re.sub(r" NOT ", Operation + " NOT ", Query)
        else:
            BCCQuery = Query + Operation
        if Print == "Lua":
            BCCQuery = "Lua:" + BCCQuery
        Param.append(BCCQuery)
