"""Shared utility functions for LangSC package."""

import os
import re
import chardet


def detect_file_encoding(file_path, sample_size=1024*10):
    """Detect file encoding by BOM or chardet."""
    with open(file_path, 'rb') as f:
        raw = f.read(4)

    if raw.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    elif raw.startswith(b'\xfe\xff'):
        return 'utf-16-be'
    elif raw.startswith(b'\xff\xfe'):
        return 'utf-16-le'
    elif raw.startswith(b'\x00\x00\xfe\xff'):
        return 'utf-32-be'
    elif raw.startswith(b'\xff\xfe\x00\x00'):
        return 'utf-32-le'

    with open(file_path, 'rb') as f:
        raw_sample = f.read(sample_size)

    result = chardet.detect(raw_sample)
    encoding = result['encoding']

    if encoding is None:
        return 'ascii'
    elif encoding.lower() == 'gb2312':
        return 'gbk'
    else:
        return encoding


def is_file_format(file_path):
    """Determine file type: 'Table', 'FSA', or 'BCC'."""
    ret = "BCC"
    try:
        with open(file_path, "rt") as f:
            no = 0
            for line in f:
                line = line.strip()
                no += 1
                if no > 100:
                    break
                if re.search('^FSA ', line):
                    ret = "FSA"
                    break
                if re.search('^Table ', line):
                    ret = "Table"
                    break
    except:
        return ret
    return ret


def is_idxed_path(path):
    """Check if a path directly contains indexed data files (non-recursive)."""
    if not os.path.isdir(path):
        return False
    for f in os.listdir(path):
        if f.find("IdxUnit.dat") != -1 or f.find("table.idx") != -1 or f.find("fsa.idx") != -1:
            return True
    return False


def get_idx_info(path, idx_log, idxed_file2time):
    """Read index log and populate idxed_file2time dict. Returns True if indexed."""
    idx_log_path = os.path.join(path, idx_log)
    if not os.path.isfile(idx_log_path):
        if is_idxed_path(path):
            return True
        return False
    with open(idx_log_path, "rt") as f:
        for line in f:
            line = line.strip()
            if line == "":
                break
            item = re.split("\t", line)
            if len(item) > 1 and not idxed_file2time.get(item[0]):
                idxed_file2time[item[0]] = {}
            for i in range(1, len(item)):
                idxed_file2time[item[0]][item[i]] = 1
    return True


def get_file_info(path, to_idx_file2time):
    """Walk path and collect file modification times."""
    for root, dirs, files in os.walk(path):
        for f in files:
            full_path = os.path.join(root, f)
            time_id = os.path.getmtime(full_path)
            if not to_idx_file2time.get(f):
                to_idx_file2time[f] = {}
            to_idx_file2time[f][str(time_id)] = 1
    return True


def is_same(to_idx_file2time, idxed_file2time):
    """Check if all files to index are already indexed with same timestamps."""
    for f, ids in to_idx_file2time.items():
        if not idxed_file2time.get(f):
            return False
        for id_ in ids:
            if not idxed_file2time[f].get(id_):
                return False
    return True


def get_gpf_files(path, idxed_file2time, table_files, fsa_files):
    """Scan path for Table and FSA files that need indexing."""
    for root, dirs, files in os.walk(path):
        for f in files:
            full_path = os.path.join(root, f)
            if idxed_file2time.get(f):
                time_id = os.path.getmtime(full_path)
                if idxed_file2time[f].get(str(time_id)):
                    continue
            fmt = is_file_format(full_path)
            if fmt == "Table":
                table_files.append(full_path)
            elif fmt == "FSA":
                fsa_files.append(full_path)


def get_bcc_files(path, idxed_file2time, bcc_files):
    """Scan path for BCC corpus files that need indexing."""
    for root, dirs, files in os.walk(path):
        for f in files:
            full_path = os.path.join(root, f)
            if idxed_file2time.get(f):
                time_id = os.path.getmtime(full_path)
                if idxed_file2time[f].get(str(time_id)):
                    continue
            fmt = is_file_format(full_path)
            if fmt != "Table" and fmt != "FSA":
                bcc_files.append(full_path)


def get_jss_file_info(path, to_idx_file2time):
    """Walk path and collect modification times for JSON/JSONL data files only."""
    for root, dirs, files in os.walk(path):
        for f in files:
            if not (f.endswith('.json') or f.endswith('.jsonl')):
                continue
            if f.startswith('cfg_'):
                continue
            full_path = os.path.join(root, f)
            time_id = os.path.getmtime(full_path)
            if not to_idx_file2time.get(f):
                to_idx_file2time[f] = {}
            to_idx_file2time[f][str(time_id)] = 1
    return True


def get_jss_files(path, idxed_file2time, jss_files):
    """Scan path for JSON/JSONL data files that need indexing."""
    for root, dirs, files in os.walk(path):
        for f in files:
            if not (f.endswith('.json') or f.endswith('.jsonl')):
                continue
            if f.startswith('cfg_'):
                continue
            full_path = os.path.join(root, f)
            if idxed_file2time.get(f):
                time_id = os.path.getmtime(full_path)
                if idxed_file2time[f].get(str(time_id)):
                    continue
            jss_files.append(full_path)


def write_idx_log(path, file_path, idx_log):
    """Write index log entry for a file."""
    idxed_file2time = {}
    get_idx_info(path, idx_log, idxed_file2time)
    time_id = os.path.getmtime(file_path)
    basename = os.path.basename(file_path)
    if not idxed_file2time.get(basename):
        idxed_file2time[basename] = {}
    idxed_file2time[basename][str(time_id)] = 1

    idx_log_path = os.path.join(path, idx_log)
    with open(idx_log_path, "wt") as out:
        for f, time_ids in idxed_file2time.items():
            print(f + "\t" + "\t".join(time_ids.keys()), file=out)


def is_file_list(filelistname):
    """Check if a file contains a list of file paths."""
    with open(filelistname, "r") as f:
        is_file = True
        is_possible = True
        for line in f:
            if not os.path.isfile(line.strip()):
                is_file = False
            if line.find("\\") == -1 and line.find("/") == -1:
                is_possible = False
    if is_file or is_possible:
        return True
    return False


def is_raw(file_path):
    """Check if a file is raw text (not Table/Doc format)."""
    encoding = detect_file_encoding(file_path)
    lines = []
    try:
        with open(file_path, "r", encoding=encoding) as f:
            no = 0
            for line in f:
                if len(line) > 20:
                    lines.append(line.strip())
                    no += 1
                    if no > 10:
                        break
    except:
        print("", end="")
    if len(lines) < 1:
        return False
    return check_lines(lines)


def check_lines(lines):
    """Check if lines represent raw text (not structured format)."""
    if lines[0].find("Table ") == 0 or lines[0].find("Doc ") == 0:
        return False
    all_words = []
    for i in range(0, len(lines)):
        words = lines[i].split(" ")
        for j in range(len(words)):
            all_words.append(words[j])
    return check_words(all_words)


def check_words(all_words):
    """Check word patterns to determine if content is raw text."""
    if len(all_words) == 0:
        return False
    num1 = 0
    num2 = 0
    word_len = 0
    for word in all_words:
        if word.find("/") != -1:
            num1 += 1
        if word.find("(") != -1 or word.find(")") != -1:
            num2 += 1
        word_len += len(word)
    avg_len = int(word_len / len(all_words))
    if num1 > int(len(all_words) * 0.9):
        return False
    if avg_len <= 4:
        return False
    if num2 > 0 and num2 > int(len(all_words) * 0.8):
        return False
    return True


def process_file(file_path, file_tmp, cmd, gpf=None):
    """Process a raw file into corpus format."""
    encoding = detect_file_encoding(file_path)
    with open(file_path, "r", encoding=encoding, errors="ignore") as f_in:
        with open(file_tmp, "w") as f_out:
            print("Doc {}".format(file_path), file=f_out)
            for line in f_in:
                line = line.strip()
                if cmd == "Convert":
                    print(line, file=f_out)
                    continue
                if cmd == "Segment" and gpf is not None:
                    sent = line.split("\u3002")
                    for s in sent:
                        s = s[0:512]
                        if len(s) == 0:
                            continue
                        result = gpf.POS(s)
                        print("Item:" + result, file=f_out)
                    continue
                sent = line.split("\u3002")
                for s in sent:
                    s = s[0:512]
                    print("Item:" + " ".join(s), file=f_out)


def file2corpus(filelist, filelist_ex, data_path, cmd, gpf=None):
    """Convert a file list into corpus format."""
    encoding = detect_file_encoding(filelist)
    with open(filelist, "r", encoding=encoding) as in_list:
        with open(filelist_ex, "w") as out_list:
            no = 0
            for file_path in in_list:
                file_path = file_path.strip()
                if is_raw(file_path):
                    file_tmp = os.path.join(data_path, os.path.basename(file_path))
                    process_file(file_path, "{}{}".format(file_tmp, no), cmd, gpf=gpf)
                    print("{}{}".format(file_tmp, no), file=out_list)
                    no += 1
                else:
                    enc = detect_file_encoding(file_path)
                    if enc != 'gbk':
                        file_tmp = os.path.join(data_path, os.path.basename(file_path))
                        process_file(file_path, "{}{}".format(file_tmp, no), "Convert")
                        print("{}{}".format(file_tmp, no), file=out_list)
                        no += 1
                    else:
                        print(file_path, file=out_list)


def corpus(path_in, filelist_names):
    """Recursively collect all files from a directory."""
    for f in os.listdir(path_in):
        abs_file = os.path.join(path_in, f)
        if os.path.isdir(abs_file):
            corpus(abs_file, filelist_names)
        else:
            filelist_names.append(abs_file)
