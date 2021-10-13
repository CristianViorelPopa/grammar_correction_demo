import streamlit as st
import language_tool_python


st.title('Grammar Correction Demo')

st.write('# LanguageTool')

with st.spinner(text='In progress'):
    tool = language_tool_python.LanguageTool('en-US')

lt_form = st.form(key='language_tool_form')
lt_text = lt_form.text_input('Exter your text here:')
lt_submit = lt_form.form_submit_button('Find mistakes')

if lt_submit:
    with st.spinner(text='In progress'):
        lt_matches = tool.check(lt_text)
        lt_corrected_text = tool.correct(lt_text)

        st.success('There were ' + str(len(lt_matches)) + ' mistakes found in the text:')
        for idx, match in enumerate(lt_matches):
            st.write(str(idx + 1) + '. __' + match.ruleIssueType.upper() + '__: "' + match.message + '"')

        st.write('The corrected text is: __"' + lt_corrected_text + '"__')

        st.write('The raw output from LanguageTool:')
        st.write(lt_matches)


st.write('# Gramformer')

st.write('TODO')
