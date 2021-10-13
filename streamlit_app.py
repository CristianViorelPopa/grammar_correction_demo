import streamlit as st
import subprocess

subprocess.call(['pip', 'install', 'git+https://github.com/PrithivirajDamodaran/Gramformer.git', '--no-deps'])

# Example
if __name__ == '__main__':
    install('argh')

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
from gramformer import Gramformer
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
