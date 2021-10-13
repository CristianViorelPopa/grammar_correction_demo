import streamlit as st
import subprocess

# subprocess.call(['pip', 'install', '--use-deprecated=legacy-resolver', 'lm-scorer'])

# subprocess.call(['pip', 'install', '--use-deprecated=legacy-resolver', 'git+https://github.com/PrithivirajDamodaran/Gramformer.git'])

# subprocess.call(['python3', '-m', 'pip', 'freeze'])


st.title('Grammar Correction Demo')

st.write('# LanguageTool')
import language_tool_python

# initial setup
with st.spinner(text='In progress'):
    tool = language_tool_python.LanguageTool('en-US')

# user form
lt_form = st.form(key='language_tool_form')
lt_text = lt_form.text_input('Enter your text here:')
lt_submit = lt_form.form_submit_button('Find mistakes')

# on form submission
if lt_submit:
    with st.spinner(text='In progress'):
        lt_matches = tool.check(lt_text)
        lt_corrected_text = tool.correct(lt_text)

        st.success('Done! There were ' + str(len(lt_matches)) + ' mistakes found in the text:')
        for idx, match in enumerate(lt_matches):
            st.write(str(idx + 1) + '. __' + match.ruleIssueType.upper() + '__: "' + match.message + '"')

        st.write('The corrected text is: __"' + lt_corrected_text + '"__')

        st.write('The raw output from LanguageTool:')
        st.write(lt_matches)


st.write('# Gramformer')


class Gramformer:

    def __init__(self, models=1, use_gpu=False):
        from transformers import AutoTokenizer
        from transformers import AutoModelForSeq2SeqLM
        from lm_scorer.models.auto import AutoLMScorer as LMScorer
        import errant
        self.annotator = errant.load('en')

        if use_gpu:
            device = "cuda:0"
        else:
            device = "cpu"
        batch_size = 1
        self.scorer = LMScorer.from_pretrained("gpt2", device=device, batch_size=batch_size)
        self.device = device
        correction_model_tag = "prithivida/grammar_error_correcter_v1"
        self.model_loaded = False

        if models == 1:
            self.correction_tokenizer = AutoTokenizer.from_pretrained(correction_model_tag)
            self.correction_model = AutoModelForSeq2SeqLM.from_pretrained(correction_model_tag)
            self.correction_model = self.correction_model.to(device)
            self.model_loaded = True
            print("[Gramformer] Grammar error correct/highlight model loaded..")
        elif models == 2:
            # TODO
            print("TO BE IMPLEMENTED!!!")

    def correct(self, input_sentence, max_candidates=1):
        if self.model_loaded:
            correction_prefix = "gec: "
            input_sentence = correction_prefix + input_sentence
            input_ids = self.correction_tokenizer.encode(input_sentence, return_tensors='pt')
            input_ids = input_ids.to(self.device)

            preds = self.correction_model.generate(
                input_ids,
                do_sample=True,
                max_length=128,
                top_k=50,
                top_p=0.95,
                early_stopping=True,
                num_return_sequences=max_candidates)

            corrected = set()
            for pred in preds:
                corrected.add(self.correction_tokenizer.decode(pred, skip_special_tokens=True).strip())

            corrected = list(corrected)
            scores = self.scorer.sentence_score(corrected, log=True)
            ranked_corrected = [(c, s) for c, s in zip(corrected, scores)]
            ranked_corrected.sort(key=lambda x: x[1], reverse=True)
            return ranked_corrected
        else:
            print("Model is not loaded")
            return None

# from gramformer import Gramformer
import torch


# initial setup
with st.spinner(text='In progress'):
    def set_seed(seed):
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


    set_seed(42)
    gf = Gramformer(models=1, use_gpu=False)

num_candidates = st.number_input('Number of candidate corrections', min_value=1, max_value=20, value=1,
                                 format='%d', help='The Gramformer is a generative model that may produce '
                                                   'more than one correction for the same sentence')

# user form
gf_form = st.form(key='language_tool_form')
gf_text = gf_form.text_input('Enter your text here:')
gf_submit = gf_form.form_submit_button('Correct the text')

# on form submission
if lt_submit:
    with st.spinner(text='In progress'):
        corrections = gf.correct(gf_text, max_candidates=num_candidates)

        st.success('Done! These are the candidate corrections by the Gramformer model:')
        for idx, correction in enumerate(corrections):
            st.write(str(idx) + '. ' + correction[0])
