import streamlit as st
import fitz  # PyMuPDF
import tempfile
import openai
from PIL import Image
import base64
import os

# --- Configuration ---
openai.api_key = st.secrets["OPENAI_API_KEY"]  # Store your key in secrets.toml

st.set_page_config(page_title="AI PDF Markup Tool", layout="wide")
st.title("AI-Powered PDF Markup Tool")
st.write("Upload a PDF and enter a prompt to get automatic markups based on your instructions.")

# --- File Upload ---
uploaded_file = st.file_uploader("Upload a PDF", type="pdf")
prompt = st.text_area("Enter your prompt (e.g., 'Highlight all temperatures above 300°C')")
submit = st.button("Generate Markups")

if uploaded_file and prompt and submit:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name

    doc = fitz.open(tmp_path)
    output_path = tmp_path.replace(".pdf", "_marked.pdf")

    st.info("Analyzing PDF... Please wait.")

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=150)
        img_path = f"/tmp/page_{page_num}.png"
        pix.save(img_path)

        with open(img_path, "rb") as img_file:
            image_bytes = img_file.read()
            encoded_image = base64.b64encode(image_bytes).decode()

            response = openai.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {"role": "system", "content": "You are a document analyst skilled in markups. Respond with bounding boxes (x0, y0, x1, y1) and comments for areas to annotate."},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}}
                    ]}
                ],
                max_tokens=1000
            )

            ai_response = response.choices[0].message.content

            st.subheader(f"Page {page_num + 1} AI Suggestions")
            st.write(ai_response)

            # Try to extract bounding boxes and comments from AI response
            lines = ai_response.split('\n')
            for line in lines:
                if "bbox" in line:
                    try:
                        bbox = eval(line.split("bbox:")[1].split("comment")[0].strip())
                        comment = line.split("comment:")[1].strip()
                        rect = fitz.Rect(*bbox)
                        page.add_highlight_annot(rect)
                        page.insert_textbox(rect, comment, fontsize=8, color=(0, 0, 1))
                    except Exception as e:
                        st.warning(f"Could not parse line: {line}")

    doc.save(output_path)
    doc.close()

    with open(output_path, "rb") as final_file:
        st.success("PDF markup complete! Download your file below.")
        st.download_button("Download Marked PDF", final_file, file_name="marked_output.pdf")

    os.remove(tmp_path)
    os.remove(output_path)
