"""Quick diagnostic to test FastEmbed"""
import sys

try:
    print("Testing FastEmbed import...")
    from fastembed import TextEmbedding
    print("✓ FastEmbed imported successfully")

    print("\nLoading embedding model...")
    embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    print("✓ Model loaded successfully")

    print("\nTesting embedding generation...")
    test_query = "AI trends in advertising"
    embedding = list(embedder.embed([test_query]))[0]
    print(f"✓ Generated embedding with {len(embedding)} dimensions")
    print(f"  First 5 values: {embedding[:5]}")

    print("\n✅ All tests passed! FastEmbed is working correctly.")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
