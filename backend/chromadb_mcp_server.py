"""
ChromaDB Inspector MCP Server
Provides tools for inspecting and debugging ChromaDB collections
"""

import asyncio
import json
import sys
from typing import Any
import chromadb
from chromadb.config import Settings
import os
from pathlib import Path

# Add MCP SDK to path if installed
try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    import mcp.server.stdio
except ImportError:
    print("Error: MCP SDK not installed. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)


class ChromaDBInspector:
    """ChromaDB inspection and debugging tools"""

    def __init__(self, default_db_path: str = "./chroma_data"):
        self.default_db_path = default_db_path
        self.client = None

    def get_client(self, db_path: str = None):
        """Get or create ChromaDB client"""
        path = db_path or self.default_db_path
        if not self.client or self.client._settings.persist_directory != path:
            self.client = chromadb.PersistentClient(path=path)
        return self.client

    def inspect_collection(self, collection_name: str = "trend_reports", db_path: str = None):
        """Get detailed collection metadata and statistics"""
        try:
            client = self.get_client(db_path)
            collection = client.get_collection(collection_name)

            count = collection.count()
            metadata = collection.metadata

            # Get sample documents to analyze
            sample_size = min(5, count)
            sample = collection.peek(limit=sample_size) if count > 0 else None

            result = {
                "name": collection_name,
                "total_documents": count,
                "metadata": metadata,
                "database_path": db_path or self.default_db_path
            }

            if sample and sample.get('metadatas'):
                # Analyze filenames
                filenames = set()
                for meta in sample['metadatas']:
                    if 'filename' in meta:
                        filenames.add(meta['filename'])
                result["sample_filenames"] = list(filenames)
                result["sample_metadata"] = sample['metadatas'][:3]

            return result
        except Exception as e:
            return {"error": str(e)}

    def list_collections(self, db_path: str = None):
        """List all collections in the database"""
        try:
            client = self.get_client(db_path)
            collections = client.list_collections()

            result = {
                "database_path": db_path or self.default_db_path,
                "total_collections": len(collections),
                "collections": []
            }

            for col in collections:
                result["collections"].append({
                    "name": col.name,
                    "count": col.count(),
                    "metadata": col.metadata
                })

            return result
        except Exception as e:
            return {"error": str(e)}

    def query_collection(self, query: str, collection_name: str = "trend_reports",
                        n_results: int = 5, db_path: str = None):
        """Query collection with semantic search"""
        try:
            client = self.get_client(db_path)
            collection = client.get_collection(collection_name)

            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )

            # Format results
            formatted_results = []
            if results['documents'] and len(results['documents']) > 0:
                for i, doc in enumerate(results['documents'][0]):
                    formatted_results.append({
                        "rank": i + 1,
                        "text_preview": doc[:200] + "..." if len(doc) > 200 else doc,
                        "full_text_length": len(doc),
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "distance": results['distances'][0][i] if results['distances'] else None
                    })

            return {
                "query": query,
                "results_count": len(formatted_results),
                "results": formatted_results
            }
        except Exception as e:
            return {"error": str(e)}

    def verify_chunks(self, filename: str, collection_name: str = "trend_reports", db_path: str = None):
        """Verify chunks for a specific PDF file"""
        try:
            client = self.get_client(db_path)
            collection = client.get_collection(collection_name)

            # Query for all chunks of this file
            all_data = collection.get(
                where={"filename": filename},
                include=["documents", "metadatas"]
            )

            if not all_data['metadatas']:
                return {"error": f"No chunks found for filename: {filename}"}

            chunks_info = []
            for i, meta in enumerate(all_data['metadatas']):
                doc_length = len(all_data['documents'][i])
                chunks_info.append({
                    "chunk_index": i,
                    "page": meta.get('page', 'unknown'),
                    "char_start": meta.get('char_start', 0),
                    "char_end": meta.get('char_end', 0),
                    "chunk_length": doc_length,
                    "text_preview": all_data['documents'][i][:100] + "..."
                })

            # Calculate overlap statistics
            overlaps = []
            for i in range(len(chunks_info) - 1):
                current_end = chunks_info[i]['char_end']
                next_start = chunks_info[i + 1]['char_start']
                overlap = current_end - next_start
                overlaps.append(overlap)

            return {
                "filename": filename,
                "total_chunks": len(chunks_info),
                "chunks": chunks_info,
                "overlap_stats": {
                    "overlaps": overlaps,
                    "avg_overlap": sum(overlaps) / len(overlaps) if overlaps else 0,
                    "min_overlap": min(overlaps) if overlaps else 0,
                    "max_overlap": max(overlaps) if overlaps else 0
                }
            }
        except Exception as e:
            return {"error": str(e)}

    def get_embedding_stats(self, collection_name: str = "trend_reports", db_path: str = None):
        """Get statistics about embeddings in the collection"""
        try:
            client = self.get_client(db_path)
            collection = client.get_collection(collection_name)

            # Get sample embeddings
            sample = collection.peek(limit=1)

            result = {
                "collection": collection_name,
                "total_documents": collection.count(),
            }

            if sample and sample.get('embeddings') and len(sample['embeddings']) > 0:
                embedding = sample['embeddings'][0]
                result["embedding_dimension"] = len(embedding)
                result["sample_embedding_preview"] = embedding[:10]
                result["embedding_model"] = collection.metadata.get('model', 'unknown')

            return result
        except Exception as e:
            return {"error": str(e)}


# Initialize MCP server
app = Server("chromadb-inspector")
inspector = ChromaDBInspector()


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available ChromaDB inspection tools"""
    return [
        Tool(
            name="inspect_collection",
            description="Get detailed metadata and statistics about a ChromaDB collection",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection_name": {
                        "type": "string",
                        "description": "Name of the collection to inspect",
                        "default": "trend_reports"
                    },
                    "db_path": {
                        "type": "string",
                        "description": "Path to ChromaDB directory (optional)"
                    }
                }
            }
        ),
        Tool(
            name="list_collections",
            description="List all collections in the ChromaDB database",
            inputSchema={
                "type": "object",
                "properties": {
                    "db_path": {
                        "type": "string",
                        "description": "Path to ChromaDB directory (optional)"
                    }
                }
            }
        ),
        Tool(
            name="query_collection",
            description="Perform semantic search query on a collection",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query text"
                    },
                    "collection_name": {
                        "type": "string",
                        "description": "Collection to search",
                        "default": "trend_reports"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "default": 5
                    },
                    "db_path": {
                        "type": "string",
                        "description": "Path to ChromaDB directory (optional)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="verify_chunks",
            description="Verify chunk quality and overlap for a specific PDF file",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "PDF filename to verify chunks for"
                    },
                    "collection_name": {
                        "type": "string",
                        "description": "Collection name",
                        "default": "trend_reports"
                    },
                    "db_path": {
                        "type": "string",
                        "description": "Path to ChromaDB directory (optional)"
                    }
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="get_embedding_stats",
            description="Get statistics about embeddings in the collection",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection_name": {
                        "type": "string",
                        "description": "Collection name",
                        "default": "trend_reports"
                    },
                    "db_path": {
                        "type": "string",
                        "description": "Path to ChromaDB directory (optional)"
                    }
                }
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Execute ChromaDB inspection tool"""
    try:
        if name == "inspect_collection":
            result = inspector.inspect_collection(
                collection_name=arguments.get("collection_name", "trend_reports"),
                db_path=arguments.get("db_path")
            )
        elif name == "list_collections":
            result = inspector.list_collections(
                db_path=arguments.get("db_path")
            )
        elif name == "query_collection":
            result = inspector.query_collection(
                query=arguments["query"],
                collection_name=arguments.get("collection_name", "trend_reports"),
                n_results=arguments.get("n_results", 5),
                db_path=arguments.get("db_path")
            )
        elif name == "verify_chunks":
            result = inspector.verify_chunks(
                filename=arguments["filename"],
                collection_name=arguments.get("collection_name", "trend_reports"),
                db_path=arguments.get("db_path")
            )
        elif name == "get_embedding_stats":
            result = inspector.get_embedding_stats(
                collection_name=arguments.get("collection_name", "trend_reports"),
                db_path=arguments.get("db_path")
            )
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({"error": str(e)}, indent=2)
        )]


async def main():
    """Run the MCP server"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
