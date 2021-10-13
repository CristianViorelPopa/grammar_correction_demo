import streamlit as st
import urllib.request
urllib.request.urlretrieve("https://download.oracle.com/java/17/latest/jdk-17_linux-x64_bin.tar.gz",
                           "jdk-17_linux-x64_bin.tar.gz")
import tarfile
tar = tarfile.open('jdk-17_linux-x64_bin.tar.gz', 'r:gz')
tar.extractall()
tar.close()
import os
app_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'jdk-17_linux-x64_bin', 'bin')
os.environ["PATH"] += os.pathsep + app_path
import language_tool_python


st.title('Grammar Correction Demo')

st.write('# LanguageTool')

with st.spinner(text='In progress'):
    tool = language_tool_python.LanguageTool('en-US')

lt_form = st.form(key='language_tool_form')
lt_text = lt_form.text_input('Text')
lt_submit = lt_form.form_submit_button('Find mistakes')

if lt_submit:
    with st.spinner(text='In progress'):
        lt_matches = tool.check(lt_text)
        lt_corrected_text = tool.correct(lt_text)

        st.success('There were ' + str(len(lt_matches)) + ' mistakes found in the text:')
        for idx, match in enumerate(lt_matches):
            st.write(str(idx) + '. ' + match.ruleIssueType.upper() + ': "' + match.message + '"')

        st.write('The corrected text is: "' + lt_corrected_text + '"')

        st.write('The raw output from LanguageTool:')
        st.write(lt_matches)


st.write('# Gramformer')

st.write('TODO')
