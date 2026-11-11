-- Migration 0012: M3 pgvector embeddings for hybrid search
-- Author: M3 (Ashwin) - ashwin-v-s
-- Date: 2026-11-05
-- Status: PROPOSAL ONLY / NOT APPLIED
-- Naming: Per D13 decision - {number}_{owner_initials}_{feature}.sql
--
-- Adds pgvector extension and embedding column to dataset table
-- for semantic search capability.

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to dataset table
ALTER TABLE dataset
ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- Create index for fast similarity search
-- Using ivfflat (inverted file with flat quantizer)
-- lists=100 is reasonable for moderate dataset sizes
CREATE INDEX IF NOT EXISTS dataset_embedding_idx
ON dataset
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Note: Embeddings are populated via application code
-- when datasets are created/updated, using OpenAI's
-- text-embedding-3-small model (1536 dimensions).

COMMENT ON COLUMN dataset.embedding IS 
'Vector embedding (1536-dim) for semantic search via OpenAI text-embedding-3-small';
