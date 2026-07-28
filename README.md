# Brittany AI Tour Guide
[![GitHub Release](https://img.shields.io/github/v/release/QuentinElGuay/portfolio-ai-tour-guide)](https://github.com/QuentinElGuay/portfolio-ai-tour-guide/releases)

Degemer mat ("Welcome" in Breton)!

This project builds an AI tour guide for Brittany, France, using **Retrieval-Augmented Generation (RAG)** to answer travelers' questions from official tourism guides.

> [!IMPORTANT]
> 🚧 This project is under **<ins>active development</ins>.**

## Table of Contents

- [Overview](#overview)
- [Dataset](#dataset)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Overview

This project was created as the capstone project for the [LLM Zoomcamp](https://github.com/DataTalksClub/llm-zoomcamp)
[DataTalks.Club](https://datatalks.club).

This project demonstrates how to build an end-to-end RAG application following modern LLM engineering practices. It indexes a tourism guide for Brittany and allows users to ask natural-language questions about the region's culture, history, geography, and attractions while grounding every answer in the source document.

The project covers document ingestion, chunking, embeddings, vector search, retrieval evaluation, prompt engineering, monitoring, and a Streamlit user interface.

## Data source
This project uses the freely available *[Discovering Brittany](https://www.ibanista.com/wp-content/uploads/2025/11/Guide-Discover-Brittany-Nov-2025.pdf)* guide published by [Ibanista](https://www.ibanista.com/). The guide is used solely for educational purposes and remains the property of its respective copyright holder. It is not redistributed as part of this repository.

## Roadmap

See the project's [roadmap](roadmap.md) *(work in progress)*.

## Contributing

This repository is maintained as a personal portfolio and learning project. While external
contributions are not currently accepted, feedback, bug reports, and suggestions are always welcome
through GitHub Issues.

## License

This repository is publicly available for educational, portfolio, and evaluation purposes.

You may browse and clone this repository to review the implementation, but the source code is **not licensed for reuse**. Unless otherwise stated,
all rights are reserved by the author. Copying, modifying, redistributing, or incorporating this code into other projects requires prior written
permission.

The tourism guide used as the knowledge source remains the property of its respective copyright holder and is not redistributed as part of this repository.
