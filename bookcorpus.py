# References
    # https://github.com/codertimo/BERT-pytorch/blob/master/bert_pytorch/dataset/dataset.py
    # https://d2l.ai/chapter_natural-language-processing-pretraining/bert-dataset.html

import os
import torch
from torch.utils.data import Dataset

from sentencepiece import parse

os.environ["TOKENIZERS_PARALLELISM"] = "true"


def _encode(x, tokenizer):
    encoding = tokenizer(
        x,
        truncation=True,
        max_length=512,
        return_token_type_ids=False,
        return_attention_mask=False,
    )
    if isinstance(x, str):
        return encoding["input_ids"][1: -1]
    else:
        return [token_ids[1: -1] for token_ids in encoding["input_ids"]]


def _token_ids_to_segment_ids(token_ids, sep_id):
    seg_ids = torch.zeros_like(token_ids, dtype=token_ids.dtype, device=token_ids.device)
    is_sep = (token_ids == sep_id)
    if is_sep.sum() == 2:
        first_sep, second_sep = is_sep.nonzero()
        # The positions from right after the first '[SEP]' token and to the second '[SEP]' token
        seg_ids[first_sep + 1: second_sep + 1] = 1
    return seg_ids


class BookCorpusForALBERT(Dataset):
    def __init__(
        self,
        epubtxt_dir,
        tokenizer,
        seq_len,
        mode="full_sentences",
    ):
        self.epubtxt_dir = epubtxt_dir
        self.tokenizer = tokenizer
        self.seq_len = seq_len
        self.mode = mode

        self.unk_id = tokenizer.unk_token_id
        self.cls_id = tokenizer.cls_token_id
        self.sep_id = tokenizer.sep_token_id
        self.pad_id = tokenizer.pad_token_id

        self.lines = parse(epubtxt_dir, with_document=True)

    def _to_bert_input(self, token_ids):
        # Add "[CLS]" and the first "[SEP]" tokens.
        token_ids = [self.cls_id] + token_ids + [self.sep_id]
        token_ids += [self.pad_id] * (self.seq_len - len(token_ids)) # Pad.
        return torch.as_tensor(token_ids)

    def __len__(self):
        return len(self.lines)

    def __getitem__(self, idx):
        new_token_ids = list()
        prev_doc = self.lines[idx][0]
        while True:
            if idx >= len(self.lines) - 1:
                break
                
            cur_doc, line = self.lines[idx]
            token_ids = _encode(line, tokenizer=self.tokenizer)
            if len(new_token_ids) + len(token_ids) >= self.seq_len - 2:
                break

            if prev_doc != cur_doc:
                new_token_ids.append(self.sep_id)

            new_token_ids.extend(token_ids)
            prev_doc = cur_doc
            idx += 1

        new_token_ids = self._to_bert_input(new_token_ids)
        # return new_token_ids
        seg_ids = _token_ids_to_segment_ids(token_ids=new_token_ids, sep_id=self.sep_id)
        return new_token_ids, seg_ids

# "We always limit the maximum input length to 512, and randomly generate input sequences
# shorter than 512 with a probability of 10%."