from llama_parse import LlamaParse
from dotenv import load_dotenv
import os
import json

load_dotenv()

parser = LlamaParse(
   api_key=os.getenv("LLAMA_API"),
   result_type="markdown",  # "markdown" and "text" are available,

   extract_charts=True,

   auto_mode=True,

   auto_mode_trigger_on_image_in_page=True,

   auto_mode_trigger_on_table_in_page=True,

   # user_prompt="If the input is not in English, translate the output into English."

   bbox_bottom=0.05 # ignores footers (bottom 5%)
   )

file_name = "./1_pipeline/parsing/or-lab_slides.pdf"
extra_info = {"file_name": file_name}

with open(f"./{file_name}", "rb") as f:
   # must provide extra_info with file_name key with passing file object
   documents = parser.load_data(f, extra_info=extra_info)

# with open('output.md', 'w') as f:
   # print(documents, file=f)

# Write the output to a file
with open("./1_pipeline/parsing/output_or.md", "w", encoding="utf-8") as f:
   for doc in documents:
       f.write(doc.text)

"""
with open("output_structured.json", "w", encoding="utf-8") as f:
    json.dump(
        [
            {
                "text": doc.text,
                "metadata": doc.metadata,
                "structure": getattr(doc, "structure", None)  # only if exists
            }
            for doc in documents
        ],
        f,
        ensure_ascii=False,
        indent=2
    )"""