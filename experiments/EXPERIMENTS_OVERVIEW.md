# Overview of Creative Studio Experiments

This document provides a summary of each application and workflow available in the `experiments` folder. Each experiment is a self-contained project designed to showcase a specific capability of Google's generative AI models.

---

### [Arena](./arena/)

*   **Purpose:** A web application for comparing and ranking different image generation models (like Imagen, Stable Diffusion) using a competitive Elo rating system and a leaderboard.
*   **Features:** Side-by-side model comparison, user voting, dynamic leaderboard, and historical performance tracking using Cloud Spanner.
*   **Tech Stack:** Mesop (Python UI), Cloud Run, Firestore, Spanner.

---

### [Babel](./babel/)

*   **Purpose:** A powerful tool for generating audio from text in all 17 of Google's Chirp 3 HD voices, with automatic translation to the correct locale for each voice.
*   **Features:** Can be used as a command-line tool, a backend web service, or a full web app.
*   **Tech Stack:** Go (for backend service/CLI), Mesop (for web app), Cloud Run.

---

### [Creative Podcast Assistant](./creative_podcast_assistant/)

*   **Purpose:** A Jupyter Notebook demonstrating a workflow for creating a podcast.
*   **Features:** Showcases how to use Speech-to-Text to transcribe audio and Text-to-Speech to generate new, clean audio for a podcast.
*   **Tech Stack:** Jupyter Notebook, Python.

---

### [Creative GenMedia Workflow](./creative-genmedia-workflow/)

*   **Purpose:** A web app that demonstrates an end-to-end workflow for generating a detailed video prompt.
*   **Features:** Takes inputs like product images, brand guidelines, and a creative brief to produce a high-quality, on-brand video prompt ready for a model like Veo.
*   **Tech Stack:** Mesop (Python UI), Cloud Run, Google Cloud Storage.

---

### [Imagen Product Recontext](./Imagen_Product_Recontext/)

*   **Purpose:** A set of Jupyter Notebooks for placing product images into new scenes at a large scale (product recontextualization).
*   **Features:** Includes a batch generation pipeline and a comprehensive framework for evaluating the quality of the generated images on axes like product fidelity, scene realism, and brand integrity.
*   **Tech Stack:** Jupyter Notebook, Python, Vertex AI, Imagen.

---

### [MCP GenMedia](./mcp-genmedia/)

*   **Purpose:** A collection of servers that expose Google's generative media APIs (Imagen, Veo, Chirp, Lyria) and an AV compositing tool through the Model Context Protocol (MCP).
*   **Features:** Makes it easier to integrate Google's powerful media generation capabilities into AI agents and other applications that support MCP.
*   **Tech Stack:** Go, Model Context Protocol (MCP).

---

### [Promptlandia](./promptlandia/)

*   **Purpose:** A web app designed to help users improve their prompt engineering skills.
*   **Features:** Includes an AI-powered prompt improver, a "prompt health checklist" that evaluates prompts against best practices, and a playground for experimentation.
*   **Tech Stack:** Mesop (Python UI), Cloud Run.

---

### [Veo Genetic Prompt Optimizer](./veo-genetic-prompt-optimizer/)

*   **Purpose:** A comprehensive guide and set of resources for mastering prompt engineering for the Veo video generation model.
*   **Features:** Provides a detailed breakdown of all the components of a good video prompt, from subject and action to advanced cinematic techniques.
*   **Tech Stack:** Markdown guide (likely accompanied by Python/Jupyter tools).

---

### [Veo3 Character Consistency](./veo3-character-consistency/)

*   **Purpose:** A sophisticated, multi-model workflow that generates a video of a specific person in a new scene while maintaining their appearance.
*   **Features:** Uses a multi-step process of image analysis, new image generation, intelligent image selection, and final video generation to achieve character consistency.
*   **Tech Stack:** Python, Gemini, Imagen, Veo.

---

### [Veo3 Item Consistency](./veo3-item-consistency/)

*   **Purpose:** A workflow similar to character consistency, but designed to maintain the appearance of a specific *item* or product in a new video scene.
*   **Features:** Essential for marketing and advertising use cases where brand and product integrity is crucial.
*   **Tech Stack:** Python, Gemini, Imagen, Veo.

---

### [VeoStart](./VeoStart/)

*   **Purpose:** A simple, self-contained HTML file that acts as a "prompting assistant" for Veo.
*   **Features:** Helps users build high-quality video prompts through a structured interface, with a gallery of examples for inspiration. It's extremely portable and easy to run.
*   **Tech Stack:** Single HTML file with JavaScript and CSS.
