import streamlit as st


st.title('Grammar Correction Demo')

# st.write('# LanguageTool')
# import language_tool_python


# @st.cache(allow_output_mutation=True)
# def setup_language_tool():
#     return language_tool_python.LanguageTool('en-US')
#
#
# # initial setup
# with st.spinner(text='In progress'):
#     tool = setup_language_tool()
#
# # user form
# with st.form(key='language_tool_form'):
#     lt_text = st.text_input('Enter your text here:')
#     lt_submit = st.form_submit_button('Find mistakes')
#
#     # on form submission
#     if lt_submit:
#         # with st.spinner(text='In progress'):
#         lt_matches = tool.check(lt_text)
#         lt_corrected_text = tool.correct(lt_text)
#
#         st.success('Done! There were ' + str(len(lt_matches)) + ' mistakes found in the text:')
#         for idx, match in enumerate(lt_matches):
#             st.write(str(idx + 1) + '. __' + match.ruleIssueType.upper() + '__: "' + match.message + '"')
#
#         st.write('The corrected text is: __"' + lt_corrected_text + '"__')
#
#         st.write('The raw output from LanguageTool:')
#         st.write(lt_matches)


st.write('# GEC-T5')

# from gramformer import Gramformer
import torch
from transformers import AutoTokenizer, GPT2LMHeadModel
from transformers import GPT2_PRETRAINED_CONFIG_ARCHIVE_MAP
from transformers.tokenization_utils import BatchEncoding
import os
from typing import *
from abc import abstractmethod, ABC
import math
import itertools


class LMScorer(ABC):
    def __init__(self, model_name: str, **kwargs: Any) -> None:
        self._build(model_name, kwargs)

    @overload
    def sentence_score(
        self, text: str, log: bool = False, reduce: str = "prod"
    ) -> float:
        ...

    @overload
    def sentence_score(
        self, text: List[str], log: bool = False, reduce: str = "prod"
    ) -> List[float]:
        ...

    def sentence_score(
        self, text: Union[str, List[str]], log: bool = False, reduce: str = "prod",
    ) -> Union[float, List[float]]:
        sentences = [text] if isinstance(text, str) else text
        scores: List[float] = []
        if len(sentences) == 0:
            return scores

        outputs = self._tokens_log_prob(sentences)
        for output in outputs:
            log_probs = output[0]
            tlen = log_probs.shape[0]

            if reduce == "prod":
                score = log_probs.sum()
            elif reduce == "mean":
                score = log_probs.logsumexp(0) - math.log(tlen)
            elif reduce == "gmean":
                score = log_probs.mean(0)
            elif reduce == "hmean":
                score = log_probs.neg().logsumexp(0).neg() + math.log(tlen)
            else:
                raise ValueError("Unrecognized scoring strategy: %s" % reduce)
            if not log:
                score = score.exp()

            scores.append(score.item())

        return scores[0] if isinstance(text, str) else scores

    @overload
    def tokens_score(
        self, text: str, log: bool = False
    ) -> Tuple[List[float], List[int], List[str]]:
        ...

    @overload
    def tokens_score(
        self, text: List[str], log: bool = False
    ) -> List[Tuple[List[float], List[int], List[str]]]:
        ...

    def tokens_score(
        self, text: Union[str, List[str]], log: bool = False
    ) -> Union[
        Tuple[List[float], List[int], List[str]],
        List[Tuple[List[float], List[int], List[str]]],
    ]:
        sentences = [text] if isinstance(text, str) else text
        outputs: List[Tuple[List[float], List[int], List[str]]] = []
        if len(sentences) == 0:
            return outputs

        for log_probs, ids, tokens in self._tokens_log_prob(sentences):
            scores = log_probs if log else log_probs.exp()
            scores = cast(torch.DoubleTensor, scores)
            output = (scores.tolist(), ids.tolist(), tokens)
            outputs.append(output)

        return outputs[0] if isinstance(text, str) else outputs

    @classmethod
    def supported_model_names(cls) -> Iterable[str]:
        return cls._supported_model_names()

    def _build(self, model_name: str, options: Dict[str, Any]) -> None:
        # pylint: disable=attribute-defined-outside-init, unused-argument
        self.model_name = model_name

    @abstractmethod
    def _tokens_log_prob(
        self, text: List[str]
    ) -> List[Tuple[torch.DoubleTensor, torch.LongTensor, List[str]]]:
        ...  # pragma: no cover

    @classmethod
    @abstractmethod
    def _supported_model_names(cls) -> Iterable[str]:
        ...  # pragma: no cover


class BatchedLMScorer(LMScorer):
    # @overrides
    def _build(self, model_name: str, options: Dict[str, Any]) -> None:
        super()._build(model_name, options)

        batch_size = options.get("batch_size", 1)
        if batch_size < 1:
            raise ValueError("The batch_size option must be positive")
        # pylint: disable=attribute-defined-outside-init
        self.batch_size = batch_size

    # @overrides
    def _tokens_log_prob(
        self, text: List[str]
    ) -> List[Tuple[torch.DoubleTensor, torch.LongTensor, List[str]]]:
        outputs = []
        for i in range(0, len(text), self.batch_size):
            batch = text[i : i + self.batch_size]
            outputs.extend(self._tokens_log_prob_for_batch(batch))
        return outputs

    @abstractmethod
    def _tokens_log_prob_for_batch(
        self, text: List[str]
    ) -> List[Tuple[torch.DoubleTensor, torch.LongTensor, List[str]]]:
        ...  # pragma: no cover


class TransformersLMScorer(BatchedLMScorer):
    # @overrides
    def _build(self, model_name: str, options: Dict[str, Any]) -> None:
        super()._build(model_name, options)

        #  Make transformers cache path configurable.
        cache_dir = os.environ.get("TRANSFORMERS_CACHE_DIR", ".transformers_cache")
        options["cache_dir"] = options.get("cache_dir", cache_dir)


class GPT2LMScorer(TransformersLMScorer):
    # @overrides
    def _build(self, model_name: str, options: Dict[str, Any]) -> None:
        super()._build(model_name, options)

        # pylint: disable=attribute-defined-outside-init
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, use_fast=True, add_special_tokens=False
        )
        # Add the pad token to GPT2 dictionary.
        # len(tokenizer) = vocab_size + 1
        self.tokenizer.add_special_tokens({"additional_special_tokens": ["<|pad|>"]})
        self.tokenizer.pad_token = "<|pad|>"

        self.model = GPT2LMHeadModel.from_pretrained(model_name)
        # We need to resize the embedding layer because we added the pad token.
        self.model.resize_token_embeddings(len(self.tokenizer))
        self.model.eval()
        if "device" in options:
            self.model.to(options["device"])

    def _add_special_tokens(self, text: str) -> str:
        return self.tokenizer.bos_token + text + self.tokenizer.eos_token

    # @overrides
    def _tokens_log_prob_for_batch(
        self, text: List[str]
    ) -> List[Tuple[torch.DoubleTensor, torch.LongTensor, List[str]]]:
        outputs: List[Tuple[torch.DoubleTensor, torch.LongTensor, List[str]]] = []
        if len(text) == 0:
            return outputs

        # TODO: Handle overflowing elements for long sentences
        text = list(map(self._add_special_tokens, text))
        encoding: BatchEncoding = self.tokenizer.batch_encode_plus(
            text, return_tensors="pt",
        )
        with torch.no_grad():
            ids = encoding["input_ids"].to(self.model.device)
            attention_mask = encoding["attention_mask"].to(self.model.device)
            nopad_mask = ids != self.tokenizer.pad_token_id
            logits: torch.Tensor = self.model(ids, attention_mask=attention_mask)[0]

        for sent_index in range(len(text)):
            sent_nopad_mask = nopad_mask[sent_index]
            # len(tokens) = len(text[sent_index]) + 1
            sent_tokens = [
                tok
                for i, tok in enumerate(encoding.tokens(sent_index))
                if sent_nopad_mask[i] and i != 0
            ]

            # sent_ids.shape = [len(text[sent_index]) + 1]
            sent_ids = ids[sent_index, sent_nopad_mask][1:]
            # logits.shape = [len(text[sent_index]) + 1, vocab_size]
            sent_logits = logits[sent_index, sent_nopad_mask][:-1, :]
            sent_logits[:, self.tokenizer.pad_token_id] = float("-inf")
            # ids_scores.shape = [seq_len + 1]
            sent_ids_scores = sent_logits.gather(1, sent_ids.unsqueeze(1)).squeeze(1)
            # log_prob.shape = [seq_len + 1]
            sent_log_probs = sent_ids_scores - sent_logits.logsumexp(1)

            sent_log_probs = cast(torch.DoubleTensor, sent_log_probs)
            sent_ids = cast(torch.LongTensor, sent_ids)

            output = (sent_log_probs, sent_ids, sent_tokens)
            outputs.append(output)

        return outputs

    # @overrides
    @classmethod
    def _supported_model_names(cls) -> Iterable[str]:
        return GPT2_PRETRAINED_CONFIG_ARCHIVE_MAP.keys()


class AutoLMScorer:
    MODEL_CLASSES = [GPT2LMScorer]

    def __init__(self):
        raise EnvironmentError(
            "AutoLMscorer is designed to be instantiated "
            "using the `AutoLMscorer.from_pretrained(model_name)`"
            "method"
        )

    @classmethod
    def from_pretrained(cls, model_name: str, **kwargs: Any):
        for model_class in cls.MODEL_CLASSES:
            if model_name not in model_class.supported_model_names():
                continue
            return model_class(model_name, **kwargs)
        raise ValueError(
            "Unrecognized model name."
            "Can be one of: %s" % ", ".join(cls.supported_model_names()),
        )

    @classmethod
    def supported_model_names(cls) -> Iterable[str]:
        classes = cls.MODEL_CLASSES
        models = map(lambda c: c.supported_model_names(), classes)
        return itertools.chain.from_iterable(models)
#
#
# class Gramformer:
#
#     def __init__(self, models=1, use_gpu=False):
#         from transformers import AutoTokenizer
#         from transformers import AutoModelForSeq2SeqLM
#         # from lm_scorer.models.auto import AutoLMScorer as LMScorer
#         import errant
#         self.annotator = errant.load('en')
#
#         if use_gpu:
#             device = "cuda:0"
#         else:
#             device = "cpu"
#         batch_size = 1
#         self.scorer = AutoLMScorer.from_pretrained("gpt2", device=device, batch_size=batch_size)
#         self.device = device
#         correction_model_tag = "prithivida/grammar_error_correcter_v1"
#         self.model_loaded = False
#
#         if models == 1:
#             self.correction_tokenizer = AutoTokenizer.from_pretrained(correction_model_tag)
#             self.correction_model = AutoModelForSeq2SeqLM.from_pretrained(correction_model_tag)
#             self.correction_model = self.correction_model.to(device)
#             self.model_loaded = True
#             print("[Gramformer] Grammar error correct/highlight model loaded..")
#         elif models == 2:
#             # TODO
#             print("TO BE IMPLEMENTED!!!")
#
#     def correct(self, input_sentence, max_candidates=1, num_beams=1, top_k=50, top_p=1.0, temperature=1.0):
#         if self.model_loaded:
#             correction_prefix = "gec: "
#             input_sentence = correction_prefix + input_sentence
#             input_ids = self.correction_tokenizer.encode(input_sentence, return_tensors='pt')
#             input_ids = input_ids.to(self.device)
#
#             preds = self.correction_model.generate(
#                 input_ids,
#                 do_sample=True,
#                 max_length=128,
#                 top_k=top_k,
#                 top_p=top_p,
#                 temperature=temperature,
#                 early_stopping=True,
#                 num_return_sequences=max_candidates,
#                 num_beams=num_beams)
#
#             corrected = set()
#             for pred in preds:
#                 corrected.add(self.correction_tokenizer.decode(pred, skip_special_tokens=True).strip())
#
#             corrected = list(corrected)
#             scores = self.scorer.sentence_score(corrected, log=True)
#             ranked_corrected = [(c, s) for c, s in zip(corrected, scores)]
#             ranked_corrected.sort(key=lambda x: x[1], reverse=True)
#             return ranked_corrected
#         else:
#             print("Model is not loaded")
#             return None
#
#
# @st.cache(allow_output_mutation=True)
# def setup_gramformer():
#     from spacy.cli import download
#     download('en')
#
#     def set_seed(seed):
#         torch.manual_seed(seed)
#         if torch.cuda.is_available():
#             torch.cuda.manual_seed_all(seed)
#
#     set_seed(42)
#     return Gramformer(models=1, use_gpu=False)


from transformers import T5ForConditionalGeneration, T5Tokenizer


@st.cache(allow_output_mutation=True)
def setup_gecT5():
    model = T5ForConditionalGeneration.from_pretrained("Unbabel/gec-t5_small")
    tokenizer = T5Tokenizer.from_pretrained('t5-small')
    scorer = AutoLMScorer.from_pretrained("gpt2", device='cpu', batch_size=1)
    return tokenizer, model, scorer


# initial setup
with st.spinner(text='In progress'):
    # gf = setup_gramformer()
    gect5_tokenizer, gect5_model, gect5_scorer = setup_gecT5()

num_candidates = st.number_input('Number of candidate corrections', min_value=1, max_value=20, value=1,
                                 format='%d', help='GEC-T5 is a generative model that may produce '
                                                   'more than one correction for the same sentence')

num_beams = st.number_input('Number of beams for text generation', min_value=1, max_value=10, value=1,
                            format='%d', help='Usually the more beams the better. Here\'s an article to understand the mechanisms of beam search: https://towardsdatascience.com/an-intuitive-explanation-of-beam-search-9b1d744e7a0f. Note that 1 beam means no beam search, so it\' a different way of generation. Here\'s another useful article: https://towardsdatascience.com/decoding-strategies-that-you-need-to-know-for-response-generation-ba95ee0faadc.')

top_k = st.slider('Top-k', min_value=10, max_value=100, value=50,
                 help='The model top-k parameter (read https://towardsdatascience.com/decoding-strategies-that-you-need-to-know-for-response-generation-ba95ee0faadc)')

top_p = st.slider('Top-p', min_value=0.5, max_value=1.0, value=1.0,
                 help='The model top-p parameter (read https://towardsdatascience.com/decoding-strategies-that-you-need-to-know-for-response-generation-ba95ee0faadc)')

temperature = st.slider('Temperature', min_value=0.3, max_value=2.0, value=1.0,
                        help='The model temperature parameter (read https://towardsdatascience.com/decoding-strategies-that-you-need-to-know-for-response-generation-ba95ee0faadc)')

# user form
with st.form(key='gect5'):
    correction_text = st.text_input('Enter your text here:')
    correction_submit = st.form_submit_button('Correct the text')

    # on form submission
    if correction_submit:
        # with st.spinner(text='In progress'):
        # corrections = gf.correct(gf_text, max_candidates=num_candidates, num_beams=num_beams, top_k=top_k, top_p=top_p, temperature=temperature)

        tokenized_sentence = gect5_tokenizer('gec: ' + correction_text, max_length=128, truncation=True,
                                             padding='max_length', return_tensors='pt')
        tokenized_corrections = gect5_model.generate(
            input_ids=tokenized_sentence.input_ids,
            attention_mask=tokenized_sentence.attention_mask,
            do_sample=True,
            max_length=128,
            top_k=top_k,
            top_p=top_p,
            temperature=temperature,
            num_beams=num_beams,
            early_stopping=True,
            num_return_sequences=num_candidates
        )

        corrections = []
        for tokenized_correction in tokenized_corrections:
            corrections.append(gect5_tokenizer.decode(
                tokenized_correction,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True
            ))
        corrections = list(set(corrections))

        scores = []
        for correction in corrections:
            scores.append(gect5_scorer.sentence_score(correction, log=True))

        ranked_corrected = [(c, s) for c, s in zip(corrections, scores)]
        ranked_corrected.sort(key=lambda x: x[1], reverse=True)

        st.success('Done! These are the candidate corrections by the GEC-T5 model:')
        for idx, correction in enumerate(ranked_corrected):
            st.write(str(idx + 1) + '. "' + correction[0] + '" with a score of ' + str(correction[1]))
