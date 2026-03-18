"""
Tests for the similarity module.
Covers min-max normalisation, cosine similarity computation,
top-K recommendations, and the build_recommendations convenience function.
"""

from __future__ import annotations

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pyspark.sql.types import DoubleType, StringType, StructField, StructType

from src.similarity import (
    build_recommendations,
    compute_cosine_similarity,
    get_top_k_recommendations,
    normalize_features,
)


class TestNormalizeFeatures:
    """Validate min-max feature normalisation."""

    def _make_agg_df(self, spark):
        """3 users with known feature values."""
        schema = StructType([
            StructField("user_id", StringType(), False),
            StructField("accuracy_rate", DoubleType(), True),
            StructField("avg_response_time_ms", DoubleType(), True),
            StructField("total_interactions", DoubleType(), True),
        ])
        data = [
            ("u001", 0.8, 15000.0, 10.0),
            ("u002", 0.4, 30000.0, 5.0),
            ("u003", 1.0, 10000.0, 20.0),
        ]
        return spark.createDataFrame(data, schema)

    def test_normalized_values_in_0_1(self, spark):
        """All normalised columns should be in [0, 1]."""
        print("\n[TEST] test_normalized_values_in_0_1")

        df = self._make_agg_df(spark)
        features = ["accuracy_rate", "avg_response_time_ms", "total_interactions"]
        normed = normalize_features(df, features)

        from pyspark.sql import functions as F
        for col_name in features:
            norm_col = f"{col_name}_norm"
            assert norm_col in normed.columns
            stats = normed.agg(
                F.min(norm_col).alias("mn"),
                F.max(norm_col).alias("mx"),
            ).first()
            assert stats["mn"] >= -0.001  # floating-point tolerance
            assert stats["mx"] <= 1.001
            print(f"  ✓ {norm_col} range [{stats['mn']:.4f}, {stats['mx']:.4f}] ⊆ [0, 1]")

    def test_min_maps_to_zero_max_to_one(self, spark):
        """The user with max value should normalise to 1, min to 0."""
        print("\n[TEST] test_min_maps_to_zero_max_to_one")

        df = self._make_agg_df(spark)
        normed = normalize_features(df, ["accuracy_rate"])

        # u003 has accuracy_rate=1.0 (max), u002 has 0.4 (min)
        u003 = normed.filter(normed.user_id == "u003").first()
        u002 = normed.filter(normed.user_id == "u002").first()

        assert abs(u003["accuracy_rate_norm"] - 1.0) < 0.001
        print("  ✓ max user normalises to ~1.0")
        assert abs(u002["accuracy_rate_norm"] - 0.0) < 0.001
        print("  ✓ min user normalises to ~0.0")

    def test_user_id_preserved(self, spark):
        """user_id column must survive normalisation."""
        print("\n[TEST] test_user_id_preserved")

        df = self._make_agg_df(spark)
        normed = normalize_features(df, ["accuracy_rate"])
        assert "user_id" in normed.columns
        assert normed.count() == 3
        print("  ✓ user_id and row count preserved")


class TestCosineSimilarity:
    """Validate pairwise cosine similarity computation."""

    def _make_vectors(self, spark):
        """3 users with known normalised vectors."""
        schema = StructType([
            StructField("user_id", StringType(), False),
            StructField("f1_norm", DoubleType(), True),
            StructField("f2_norm", DoubleType(), True),
        ])
        data = [
            ("u001", 1.0, 0.0),
            ("u002", 0.0, 1.0),
            ("u003", 1.0, 0.0),  # identical to u001
        ]
        return spark.createDataFrame(data, schema)

    def test_similarity_output_columns(self, spark):
        """Output should have user_id, other_user_id, similarity_score."""
        print("\n[TEST] test_similarity_output_columns")

        df = self._make_vectors(spark)
        sim = compute_cosine_similarity(df, ["f1", "f2"])
        assert "user_id" in sim.columns
        assert "other_user_id" in sim.columns
        assert "similarity_score" in sim.columns
        print("  ✓ all expected similarity columns present")

    def test_identical_vectors_have_score_one(self, spark):
        """u001 and u003 have identical vectors → similarity ≈ 1.0."""
        print("\n[TEST] test_identical_vectors_have_score_one")

        df = self._make_vectors(spark)
        sim = compute_cosine_similarity(df, ["f1", "f2"])

        pair = sim.filter(
            ((sim.user_id == "u001") & (sim.other_user_id == "u003"))
            | ((sim.user_id == "u003") & (sim.other_user_id == "u001"))
        ).first()

        assert pair is not None, "Expected pair (u001, u003) in output"
        assert abs(pair["similarity_score"] - 1.0) < 0.01
        print(f"  ✓ similarity(u001, u003) = {pair['similarity_score']:.4f} ≈ 1.0")

    def test_orthogonal_vectors_have_score_zero(self, spark):
        """u001=[1,0] and u002=[0,1] are orthogonal → similarity ≈ 0.0."""
        print("\n[TEST] test_orthogonal_vectors_have_score_zero")

        df = self._make_vectors(spark)
        sim = compute_cosine_similarity(df, ["f1", "f2"])

        pair = sim.filter(
            ((sim.user_id == "u001") & (sim.other_user_id == "u002"))
            | ((sim.user_id == "u002") & (sim.other_user_id == "u001"))
        ).first()

        assert pair is not None
        assert abs(pair["similarity_score"]) < 0.01
        print(f"  ✓ similarity(u001, u002) = {pair['similarity_score']:.4f} ≈ 0.0")

    def test_no_self_pairs(self, spark):
        """No user should appear as their own recommendation."""
        print("\n[TEST] test_no_self_pairs")

        df = self._make_vectors(spark)
        sim = compute_cosine_similarity(df, ["f1", "f2"])

        self_pairs = sim.filter(sim.user_id == sim.other_user_id).count()
        assert self_pairs == 0
        print("  ✓ no self-pairs in similarity output")


class TestTopKRecommendations:
    """Validate top-K ranking and filtering."""

    def _make_sim_df(self, spark):
        """Pre-built similarity DataFrame for testing top-K."""
        schema = StructType([
            StructField("user_id", StringType(), False),
            StructField("other_user_id", StringType(), False),
            StructField("similarity_score", DoubleType(), True),
        ])
        data = [
            ("u001", "u002", 0.9),
            ("u001", "u003", 0.5),
            ("u001", "u004", 0.3),
            ("u002", "u001", 0.9),
            ("u002", "u003", 0.7),
            ("u002", "u004", 0.1),
            ("u003", "u001", 0.5),
            ("u003", "u002", 0.7),
            ("u003", "u004", 0.6),
        ]
        return spark.createDataFrame(data, schema)

    def test_top_k_limits_recommendations(self, spark):
        """Each user should have at most top_k recommendations."""
        print("\n[TEST] test_top_k_limits_recommendations")

        sim_df = self._make_sim_df(spark)
        top2 = get_top_k_recommendations(sim_df, top_k=2)

        from pyspark.sql import functions as F
        max_per_user = top2.groupBy("user_id").agg(
            F.count("*").alias("cnt")
        ).agg(F.max("cnt")).first()[0]

        assert max_per_user <= 2
        print(f"  ✓ max recommendations per user = {max_per_user} <= 2")

    def test_top_k_selects_highest_scores(self, spark):
        """Top-K should keep the highest similarity scores."""
        print("\n[TEST] test_top_k_selects_highest_scores")

        sim_df = self._make_sim_df(spark)
        top1 = get_top_k_recommendations(sim_df, top_k=1)

        # u001's top match should be u002 (score=0.9)
        u001_rec = top1.filter(top1.user_id == "u001").first()
        assert u001_rec["recommended_user_id"] == "u002"
        assert abs(u001_rec["similarity_score"] - 0.9) < 0.01
        print("  ✓ u001 top-1 is u002 with score 0.9")

    def test_rank_column_present(self, spark):
        """Output should include a 'rank' column."""
        print("\n[TEST] test_rank_column_present")

        sim_df = self._make_sim_df(spark)
        top2 = get_top_k_recommendations(sim_df, top_k=2)

        assert "rank" in top2.columns
        print("  ✓ 'rank' column present in top-K output")


class TestBuildRecommendations:
    """Validate the end-to-end build_recommendations convenience function."""

    def test_returns_vectors_and_recs(self, spark):
        """build_recommendations should return (user_vectors, recommendations_batch)."""
        print("\n[TEST] test_returns_vectors_and_recs")

        schema = StructType([
            StructField("user_id", StringType(), False),
            StructField("accuracy_rate", DoubleType(), True),
            StructField("avg_response_time_ms", DoubleType(), True),
            StructField("total_interactions", DoubleType(), True),
        ])
        data = [
            ("u001", 0.8, 15000.0, 10.0),
            ("u002", 0.4, 30000.0, 5.0),
            ("u003", 1.0, 10000.0, 20.0),
        ]
        agg_df = spark.createDataFrame(data, schema)

        features = ["accuracy_rate", "avg_response_time_ms", "total_interactions"]
        vectors, recs = build_recommendations(agg_df, features, top_k=2)

        assert vectors.count() == 3
        print("  ✓ user_vectors has 3 rows")

        assert "user_id" in recs.columns
        assert "recommended_user_id" in recs.columns
        print("  ✓ recommendations_batch has expected columns")

        assert recs.count() > 0
        print(f"  ✓ recommendations_batch has {recs.count()} rows")
