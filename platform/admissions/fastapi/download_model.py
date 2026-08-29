#!/usr/bin/env python3
"""
Pre-download BGE-Large-EN-v1.5 embedding model into the container image.
Called at Docker build time so runtime has zero cold-start model download.
"""
from sentence_transformers import SentenceTransformer

MODEL_ID = "BAAI/bge-large-en-v1.5"
print(f"Downloading {MODEL_ID} ...")
model = SentenceTransformer(MODEL_ID)
print(f"Model cached at: {model._modules}")
print("Done.")
