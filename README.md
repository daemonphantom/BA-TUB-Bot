# INSTALLATION

three venvs: 
1. pipeline-env: pip install requirements-pipeline.txt
2. mpv-env: pip install requirements-mvp.txt
3. transcribe-env: ...


# TutorAI: A Smart Assistant for TU Berlin

Welcome to **TutorAI**, a research-driven project developed as part of my Bachelor’s thesis at **Technische Universität Berlin**. This system is designed to build an intelligent assistant that helps both **students** and **teachers** engage more effectively with university course content.

---

## 🚀 Project Vision

**TutorAI** is not just a chatbot. It's a dual-purpose AI assistant:

- 🎓 **For Students**: TutorAI helps answer course-related questions, provides explanations, and assists with exercises—acting as a virtual tutor trained on actual course materials.
- 🧑‍🏫 **For Teachers**: It also supports teaching staff by suggesting improvements to materials, tracking content versions over time, and even generating new exercises or quizzes.

Think of it as an **educational co-pilot** for TU Berlin’s Faculty IV.

---

## 🧠 Thesis Objective

The main goal of this thesis is to explore how modern NLP and AI tools—like large language models, vector search, and knowledge graphs—can be combined to build a **domain-specific assistant**. Unlike general-purpose LLMs, TutorAI is trained exclusively on TU Berlin course materials to provide **accurate, context-aware** support.

---

## 🛠️ Tech Stack

| Tool / Library        | Purpose                                   |
|-----------------------|-------------------------------------------|
| `Python`              | Core language for all components          |
| `Llama 3`             | Large Language Model (via Llama.cpp or Ollama) |
| `LlamaIndex` / `FAISS`| Vector-based semantic search              |
| `Neo4j` / `NetworkX`  | Knowledge graph construction and querying |
| `BeautifulSoup`       | Crawling TU’s ISIS platform               |
| `Scrapy`              | Scalable web scraping                     |
| `PyMuPDF`             | Extracting text from PDFs                 |
| `Whisper`             | Transcribing lecture videos               |

---

## 🔍 Features

- ✅ Intelligent crawling of TU Berlin's ISIS course pages
- ✅ Parsing announcements, quizzes, forums, videos, and more
- ✅ Structured knowledge graph for version tracking & reasoning
- ✅ Semantic search with vector embeddings for quick, relevant answers
- ✅ Dynamic, on-demand crawling as needed (non-exhaustive strategy)
- ✅ Built-in flexibility to scale across multiple courses and semesters

---

## 🧪 Research Goals

- Train a domain-specific tutor for TU Berlin
- Explore the combination of **RAG** (Retrieval-Augmented Generation) and **knowledge graphs**
- Implement version tracking to model the **evolution of teaching materials**
- Contribute to the future of **AI-powered education**

---

## 💡 Why This Matters

In an era of ever-expanding information, students and instructors need **intelligent tools** to navigate content more efficiently. TutorAI is a step toward making education more responsive, personalized, and scalable.

This isn't just a bachelor's project — it's a **prototype for the future of learning** at TU Berlin.

---

## 🧭 Ethical Reflections

While developing TutorAI, I have continuously reflected on the ethical implications of AI in education. As with any powerful tool, its impact depends on how it is used. TutorAI has the potential to support deep learning, foster student independence, and reduce repetitive workload for educators. However, it also carries the risk of encouraging passive consumption or misuse, such as automating tasks that should involve critical thinking.

The core intention behind TutorAI is to augment human understanding — not to replace it. That is why the system is designed not just to give answers, but to promote interactive dialogue, offer contextual support, and encourage self-reflection. Features like version tracking and structured content graphs aim to make educational content more transparent and traceable—not disposable.

I believe that students should be guided in how to use generative AI responsibly, and educators should retain control over how such systems interact with their materials. The integration of TutorAI should therefore follow clear guidelines aligned with academic integrity and digital ethics.

Ultimately, this project is both a technical exploration and a contribution to the ongoing conversation about what education should look like in the AI age. TutorAI should not replace curiosity, mentorship, or hard-earned understanding — it should amplify them.

---

## 🙌 Acknowledgements

Special thanks to my supervisor Damien for pushing me to think bigger, go deeper, and stay focused on what matters: building useful tools that work at scale.

---

## 📫 Contact

If you're interested in collaborating, using TutorAI, or just curious about the project, feel free to reach out:

**David Durglishvili**  
`durglishvili@campus.tu-berlin.de`  
or message me on [LinkedIn](https://linkedin.com)