#!/usr/bin/env python
"""
Feature Validation Utility — v3.0.0

Lightweight EDA untuk validasi feature engineering sebelum modeling.

Fungsi:
1. Distribusi setiap feature
2. Perbandingan high-risk vs low-risk 
3. Korelasi antar feature
4. Deteksi redundansi (|corr| > threshold)
5. Laporan edge case (zero activity, missing values)

Usage:
    python -m scripts.validate_features --cutoff-date 2026-01-01
    python -m scripts.validate_features --output-dir reports/

Requires: matplotlib, seaborn, pandas, numpy
"""
import argparse
import logging
import os
import sys
from datetime import date, timedelta
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_feature_service():
    """Get FeatureService with Flask context."""
    from app import create_app
    from app.services.feature_service import FeatureService
    app = create_app()
    ctx = app.app_context()
    ctx.push()
    return FeatureService(), ctx


def load_feature_data(cutoff_date: date) -> pd.DataFrame:
    """
    Load feature data dari database.
    
    Menggunakan FeatureService.get_ml_feature_dict() untuk setiap customer.
    """
    from app import db
    from app.models.customer import Customer
    from app.models.numeric_features import CustomerNumericFeatures
    from app.services.feature_service import FeatureService

    svc = FeatureService()
    
    # Get customers with features
    customers_with_features = db.session.query(
        CustomerNumericFeatures.customer_id
    ).filter(
        CustomerNumericFeatures.as_of_date == cutoff_date
    ).distinct().all()
    
    customer_ids = [str(c[0]) for c in customers_with_features]
    
    if not customer_ids:
        logger.warning(f"No features found for cutoff_date={cutoff_date}")
        return pd.DataFrame()
    
    rows = []
    for cid in customer_ids:
        try:
            feature_dict = svc.get_ml_feature_dict(cid, cutoff_date)
            if feature_dict:
                feature_dict['customer_id'] = cid
                rows.append(feature_dict)
        except Exception as e:
            logger.debug(f"Skipping {cid}: {e}")
    
    df = pd.DataFrame(rows)
    logger.info(f"Loaded {len(df)} feature vectors for {cutoff_date}")
    return df


def validate_distributions(
    df: pd.DataFrame,
    feature_names: List[str],
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    1. Distribusi setiap feature.
    
    Menampilkan histogram + statistik deskriptif.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        logger.warning("matplotlib/seaborn not available, skipping plots")
        return {"stats": df[feature_names].describe().to_dict()}
    
    n_features = len(feature_names)
    n_cols = 4
    n_rows = (n_features + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(20, 5 * n_rows))
    axes = axes.ravel()
    
    for i, name in enumerate(feature_names):
        ax = axes[i]
        if name in df.columns:
            df[name].hist(bins=30, ax=ax, alpha=0.7, color='steelblue', edgecolor='white')
            ax.set_title(name, fontsize=10, fontweight='bold')
            
            # Add mean line
            mean_val = df[name].mean()
            ax.axvline(mean_val, color='red', linestyle='--', alpha=0.7, label=f'mean={mean_val:.2f}')
            ax.legend(fontsize=8)
    
    # Hide unused axes
    for i in range(n_features, len(axes)):
        axes[i].set_visible(False)
    
    plt.suptitle('Feature Distributions (v3.0.0)', fontsize=14, y=1.02)
    plt.tight_layout()
    
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        fig.savefig(os.path.join(output_dir, 'feature_distributions.png'), 
                    dpi=150, bbox_inches='tight')
        logger.info(f"Saved distribution plot to {output_dir}/feature_distributions.png")
    
    plt.close()
    
    stats = df[feature_names].describe()
    print("\n📊 Feature Statistics:")
    print(stats.round(3).to_string())
    
    return {"stats": stats.to_dict()}


def validate_group_comparison(
    df: pd.DataFrame,
    feature_names: List[str],
    label_col: str = "is_disengaged",
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    2. Perbandingan feature antara high-risk vs low-risk.
    
    Jika label tidak tersedia, gunakan proxy berbasis recency_days.
    """
    if label_col not in df.columns:
        # Proxy: customer dengan recency_days tinggi = high risk
        if 'recency_days' in df.columns:
            median_recency = df['recency_days'].median()
            df['_proxy_risk'] = (df['recency_days'] > median_recency).astype(int)
            label_col = '_proxy_risk'
            print("⚠️ Menggunakan proxy label (recency_days > median)")
        else:
            print("⚠️ Tidak ada label — skip group comparison")
            return {}
    
    valid_features = [f for f in feature_names if f in df.columns]
    
    comparison = pd.DataFrame({
        'Low_Risk_mean': df[df[label_col] == 0][valid_features].mean(),
        'High_Risk_mean': df[df[label_col] == 1][valid_features].mean(),
        'Low_Risk_std': df[df[label_col] == 0][valid_features].std(),
        'High_Risk_std': df[df[label_col] == 1][valid_features].std(),
    })
    
    # Perbedaan relatif
    comparison['diff_pct'] = (
        (comparison['High_Risk_mean'] - comparison['Low_Risk_mean'])
        / comparison['Low_Risk_mean'].replace(0, np.nan) * 100
    )
    
    print("\n📊 Feature Comparison: High Risk vs Low Risk")
    print(comparison.round(3).to_string())
    
    # Highlight most discriminative features
    comparison_sorted = comparison.reindex(
        comparison['diff_pct'].abs().sort_values(ascending=False).index
    )
    
    print("\n🏆 Most Discriminative Features (by |diff%|):")
    for name, row in comparison_sorted.head(5).iterrows():
        print(f"  {name}: {row['diff_pct']:+.1f}% "
              f"(Low={row['Low_Risk_mean']:.3f}, High={row['High_Risk_mean']:.3f})")
    
    return {"comparison": comparison.to_dict()}


def validate_correlations(
    df: pd.DataFrame,
    feature_names: List[str],
    redundancy_threshold: float = 0.95,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    3. Korelasi antar feature + 4. Deteksi redundansi.
    """
    valid_features = [f for f in feature_names if f in df.columns]
    corr = df[valid_features].corr()
    
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import seaborn as sns
        
        fig, ax = plt.subplots(1, 1, figsize=(14, 12))
        mask = np.triu(np.ones_like(corr, dtype=bool))
        sns.heatmap(corr, mask=mask, annot=True, fmt='.2f', cmap='RdBu_r',
                    center=0, vmin=-1, vmax=1, square=True, linewidths=0.5, ax=ax)
        ax.set_title('Feature Correlation Matrix (v3.0.0)', fontsize=14)
        plt.tight_layout()
        
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            fig.savefig(os.path.join(output_dir, 'correlation_matrix.png'),
                        dpi=150, bbox_inches='tight')
            logger.info(f"Saved correlation matrix to {output_dir}/correlation_matrix.png")
        
        plt.close()
    except ImportError:
        pass
    
    # Redundancy detection
    redundant_pairs = []
    n = len(corr.columns)
    for i in range(n):
        for j in range(i + 1, n):
            if abs(corr.iloc[i, j]) > redundancy_threshold:
                redundant_pairs.append({
                    'feature_1': corr.columns[i],
                    'feature_2': corr.columns[j],
                    'correlation': round(corr.iloc[i, j], 4)
                })
    
    print(f"\n⚠️ Redundant Pairs (|corr| > {redundancy_threshold}):")
    if redundant_pairs:
        for pair in redundant_pairs:
            print(f"  {pair['feature_1']} ↔ {pair['feature_2']}: {pair['correlation']:.4f}")
    else:
        print("  ✅ Tidak ada pasangan feature yang sangat redundan")
    
    return {
        "redundant_pairs": redundant_pairs,
        "correlation_matrix": corr.to_dict()
    }


def validate_edge_cases(
    df: pd.DataFrame,
    feature_names: List[str]
) -> Dict[str, Any]:
    """
    5. Laporan edge case.
    """
    print("\n📊 Edge Case Report:")
    
    report = {}
    
    # Missing values
    missing = df[feature_names].isnull().sum()
    total_missing = missing.sum()
    print(f"\n  Missing values: {total_missing} total")
    if total_missing > 0:
        for name in feature_names:
            if missing[name] > 0:
                pct = missing[name] / len(df) * 100
                print(f"    {name}: {missing[name]} ({pct:.1f}%)")
    report['missing_total'] = int(total_missing)
    
    # Zero activity
    for col in ['activity_mean', 'recent_activity_avg', 'tx_count_90d']:
        if col in df.columns:
            zero_count = (df[col] == 0).sum()
            pct = zero_count / len(df) * 100
            print(f"  Zero {col}: {zero_count} ({pct:.1f}%)")
            report[f'zero_{col}'] = int(zero_count)
    
    # Capped CV values
    for col in ['activity_cv', 'spend_volatility_cv']:
        if col in df.columns:
            # CV cap default = 10.0
            capped = (df[col] >= 9.99).sum()
            print(f"  Capped {col} (≥10): {capped}")
            report[f'capped_{col}'] = int(capped)
    
    # Extreme values
    print("\n  Extreme values (>3σ from mean):")
    for col in feature_names:
        if col in df.columns:
            mean = df[col].mean()
            std = df[col].std()
            if std > 0:
                outliers = ((df[col] - mean).abs() > 3 * std).sum()
                if outliers > 0:
                    pct = outliers / len(df) * 100
                    print(f"    {col}: {outliers} ({pct:.1f}%) outliers")
    
    return report


def run_full_validation(cutoff_date: date, output_dir: Optional[str] = None):
    """Run full validation pipeline."""
    print("=" * 60)
    print(f"📊 FEATURE VALIDATION — v3.0.0")
    print(f"📅 Cutoff date: {cutoff_date}")
    print("=" * 60)
    
    svc, ctx = get_feature_service()
    feature_names = svc.get_feature_names()
    
    print(f"\n📋 Schema: {svc.FEATURE_SCHEMA_VERSION}")
    print(f"📊 Features: {svc.expected_feature_count()}")
    print(f"🔧 Config: {svc.config.to_dict()}")
    
    df = load_feature_data(cutoff_date)
    
    if df.empty:
        print("\n❌ No data found — cannot run validation")
        ctx.pop()
        return
    
    print(f"\n✅ Loaded {len(df)} samples")
    
    # Run validations
    validate_distributions(df, feature_names, output_dir)
    validate_group_comparison(df, feature_names, output_dir=output_dir)
    validate_correlations(df, feature_names, output_dir=output_dir)
    validate_edge_cases(df, feature_names)
    
    print("\n" + "=" * 60)
    print("✅ Validation complete!")
    print("=" * 60)
    
    ctx.pop()


def main():
    parser = argparse.ArgumentParser(description="Feature Validation Utility v3.0.0")
    parser.add_argument(
        "--cutoff-date", type=str,
        default=(date.today() - timedelta(days=90)).isoformat(),
        help="Cutoff date for feature snapshot (default: 90 days ago)"
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Directory for output plots (optional)"
    )
    parser.add_argument(
        "--redundancy-threshold", type=float, default=0.95,
        help="Correlation threshold for redundancy detection (default: 0.95)"
    )
    
    args = parser.parse_args()
    cutoff = date.fromisoformat(args.cutoff_date)
    
    run_full_validation(cutoff, args.output_dir)


if __name__ == "__main__":
    main()
