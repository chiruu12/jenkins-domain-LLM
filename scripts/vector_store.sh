#!/bin/bash

TARGET_DIR="Jen_agent/agent_workspace/knowledge_base"
FILE_ID="1WAZSRsbO24yeU4ul3jC-BZH4gMWGO_JK"
ZIP_NAME="vector_store_backup.zip"

echo "Fetching vector store from Google Drive..."

if ! command -v unzip &> /dev/null; then
    echo "unzip not found. Install it first."
    exit 1
fi

mkdir -p "$TARGET_DIR"

gdown "$FILE_ID" -O "$ZIP_NAME"

unzip -o "$ZIP_NAME" -d "Jen_agent/"

rm "$ZIP_NAME"

echo "Vector store added to: $TARGET_DIR"
