#!/usr/bin/env python3
"""
Convert the econometrics-in-python README.md to a JSON database.
Parses markdown tables and extracts package information.
"""

import re
import json
import subprocess
import sys


def fetch_readme() -> str:
    """Fetch the raw README.md from GitHub using curl.

    Returns:
        The raw markdown content of the README file.

    Raises:
        SystemExit: If the curl command fails to fetch the README.
    """
    url = "https://raw.githubusercontent.com/rawatpranjal/econometrics-in-python/main/README.md"
    result = subprocess.run(
        ['curl', '-sL', url],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error fetching README: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def parse_links(links_cell: str) -> tuple[str | None, str | None]:
    """Extract Docs and GitHub URLs from a markdown links cell.

    Parses markdown link syntax like '[Docs](url) . [GitHub](url)' and
    categorizes URLs based on link text.

    Args:
        links_cell: A string containing markdown-formatted links.

    Returns:
        A tuple of (docs_url, github_url), where either may be None if not found.
    """
    docs_url = None
    github_url = None

    # Find all markdown links
    links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', links_cell)
    for text, url in links:
        text_lower = text.lower()
        if 'doc' in text_lower or 'pypi' in text_lower:
            docs_url = url
        elif 'github' in text_lower or 'git' in text_lower:
            github_url = url
        elif docs_url is None:
            docs_url = url  # First link as fallback

    return docs_url, github_url


# Category to tag mapping for use-case based filtering
CATEGORY_TAG_MAP: dict[str, list[str]] = {
    "Adaptive Experimentation & Bandits": ["A/B testing", "experimentation"],
    "Bayesian Econometrics": ["Bayesian", "inference"],
    "Causal Discovery & Graphical Models": ["causal inference", "graphs"],
    "Causal Inference & Matching": ["causal inference", "matching"],
    "Core Libraries & Linear Models": ["regression", "linear models"],
    "Dimensionality Reduction": ["machine learning", "dimensionality"],
    "Discrete Choice Models": ["discrete choice", "logit"],
    "Double/Debiased Machine Learning (DML)": ["machine learning", "causal inference"],
    "Instrumental Variables (IV) & GMM": ["IV", "GMM"],
    "Marketing Mix Models (MMM) & Business Analytics": ["marketing", "analytics"],
    "Natural Language Processing for Economics": ["NLP", "text analysis"],
    "Numerical Optimization & Computational Tools": ["optimization", "computation"],
    "Panel Data & Fixed Effects": ["panel data", "fixed effects"],
    "Power Simulation & Design of Experiments": ["power analysis", "experiments"],
    "Program Evaluation Methods (DiD, SC, RDD)": ["DiD", "synthetic control", "RDD"],
    "Quantile Regression & Distributional Methods": ["quantile", "regression"],
    "Spatial Econometrics": ["spatial", "geography"],
    "Standard Errors, Bootstrapping & Reporting": ["bootstrap", "standard errors"],
    "State Space & Volatility Models": ["volatility", "state space"],
    "Statistical Inference & Hypothesis Testing": ["inference", "hypothesis testing"],
    "Structural Econometrics & Estimation": ["structural", "estimation"],
    "Synthetic Data Generation": ["synthetic data", "simulation"],
    "Time Series Econometrics": ["time series", "econometrics"],
    "Time Series Forecasting": ["forecasting", "time series"],
    "Tree & Ensemble Methods for Prediction": ["machine learning", "prediction"],
}

# Category to "Best For" mapping - describes ideal use cases
CATEGORY_BEST_FOR: dict[str, str] = {
    "Adaptive Experimentation & Bandits": "Online A/B testing, multi-armed bandits, adaptive allocation",
    "Bayesian Econometrics": "Uncertainty quantification, prior-informed inference, probabilistic modeling",
    "Causal Discovery & Graphical Models": "Learning causal structure from data, DAG estimation",
    "Causal Inference & Matching": "Estimating treatment effects, propensity score matching, observational studies",
    "Core Libraries & Linear Models": "OLS regression, basic econometrics, data manipulation",
    "Dimensionality Reduction": "Feature extraction, PCA, high-dimensional data",
    "Discrete Choice Models": "Logit/probit models, consumer choice, demand estimation",
    "Double/Debiased Machine Learning (DML)": "High-dimensional controls, ML-based causal inference",
    "Instrumental Variables (IV) & GMM": "Endogeneity correction, 2SLS, moment estimation",
    "Marketing Mix Models (MMM) & Business Analytics": "Marketing ROI, media mix optimization, attribution",
    "Natural Language Processing for Economics": "Text analysis, sentiment analysis, document classification",
    "Numerical Optimization & Computational Tools": "Solving optimization problems, numerical methods",
    "Panel Data & Fixed Effects": "Longitudinal analysis, controlling for unobserved heterogeneity",
    "Power Simulation & Design of Experiments": "Sample size calculation, experimental design, power analysis",
    "Program Evaluation Methods (DiD, SC, RDD)": "Policy evaluation, natural experiments, quasi-experiments",
    "Quantile Regression & Distributional Methods": "Heterogeneous effects, distributional analysis",
    "Spatial Econometrics": "Geographic data, spatial autocorrelation, regional analysis",
    "Standard Errors, Bootstrapping & Reporting": "Robust inference, clustered SEs, result presentation",
    "State Space & Volatility Models": "GARCH, stochastic volatility, Kalman filtering",
    "Statistical Inference & Hypothesis Testing": "Hypothesis tests, confidence intervals, multiple testing",
    "Structural Econometrics & Estimation": "Structural models, GMM estimation, BLP-style demand",
    "Synthetic Data Generation": "Privacy-preserving data, simulation, augmentation",
    "Time Series Econometrics": "ARIMA, cointegration, VAR models",
    "Time Series Forecasting": "Prediction, demand forecasting, trend analysis",
    "Tree & Ensemble Methods for Prediction": "Random forests, gradient boosting, prediction tasks",
}

# Keywords in descriptions that map to additional tags
KEYWORD_TAGS: dict[str, str] = {
    "propensity": "matching",
    "treatment effect": "causal inference",
    "ARIMA": "time series",
    "GARCH": "volatility",
    "bayesian": "Bayesian",
    "neural": "machine learning",
    "deep learning": "machine learning",
    "random forest": "machine learning",
    "xgboost": "machine learning",
    "gradient boost": "machine learning",
}


def generate_tags(category: str, description: str) -> list[str]:
    """Generate use-case tags from category and description keywords.

    Args:
        category: The package category.
        description: The package description.

    Returns:
        A list of 2-4 relevant use-case tags.
    """
    tags: list[str] = []

    # Add category-based tags
    if category in CATEGORY_TAG_MAP:
        tags.extend(CATEGORY_TAG_MAP[category])

    # Add keyword-based tags from description
    desc_lower = description.lower()
    for keyword, tag in KEYWORD_TAGS.items():
        if keyword in desc_lower and tag not in tags:
            tags.append(tag)

    # Limit to 4 tags max and remove duplicates while preserving order
    seen: set[str] = set()
    unique_tags: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)
            if len(unique_tags) >= 4:
                break

    return unique_tags


def parse_readme(content: str) -> list[dict[str, str | None]]:
    """Parse the README content and extract package data.

    Processes markdown tables organized by category headers and extracts
    package information including name, description, links, and install commands.

    Args:
        content: The full markdown content of the README file.

    Returns:
        A list of package dictionaries with keys: name, description,
        category, docs_url, github_url, url, install.
    """
    packages = []
    current_category = None

    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Detect category headers (## Category Name)
        if line.startswith('## '):
            category = line[3:].strip()
            # Skip non-package sections
            if category.lower() not in ['contributing', 'learning resources', 'license', 'table of contents']:
                current_category = category

        # Detect table rows (start with |)
        if line.startswith('|') and current_category:
            # Skip header row and separator row
            if '---' in line or 'Package' in line or 'Description' in line:
                i += 1
                continue

            # Parse table row
            cells = [c.strip() for c in line.split('|')]
            cells = [c for c in cells if c]  # Remove empty cells

            if len(cells) >= 3:
                # Extract package name (remove bold markers)
                name_raw = cells[0]
                # Remove markdown bold/italic markers
                name = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', name_raw).strip()

                if not name or name.lower() in ['package', 'name']:
                    i += 1
                    continue

                description = cells[1].strip() if len(cells) > 1 else ""
                links_cell = cells[2] if len(cells) > 2 else ""
                install_cmd = cells[3] if len(cells) > 3 else ""

                # Clean install command
                install_cmd = re.sub(r'`([^`]+)`', r'\1', install_cmd).strip()

                # Parse links
                docs_url, github_url = parse_links(links_cell)

                # Use first available URL as primary
                primary_url = github_url or docs_url or f"https://pypi.org/project/{name}/"

                packages.append({
                    "name": name,
                    "description": description,
                    "category": current_category,
                    "docs_url": docs_url,
                    "github_url": github_url,
                    "url": primary_url,
                    "install": install_cmd
                })

        i += 1

    return packages


def main() -> None:
    """Main entry point for the README conversion script.

    Fetches the upstream README, parses packages, removes duplicates,
    and saves the result to data/packages.json.
    """
    print("Fetching README from GitHub...")
    content = fetch_readme()

    print("Parsing packages...")
    packages = parse_readme(content)

    # Remove duplicates by name and add tags + best_for
    seen = set()
    unique_packages = []
    for pkg in packages:
        if pkg['name'] not in seen:
            seen.add(pkg['name'])
            # Generate use-case tags for each package
            pkg['tags'] = generate_tags(pkg['category'], pkg['description'])
            # Add "best for" field from category mapping
            pkg['best_for'] = CATEGORY_BEST_FOR.get(pkg['category'], "")
            unique_packages.append(pkg)

    # Sort by category then name
    unique_packages.sort(key=lambda x: (x['category'], x['name']))

    # Save to data directory
    output_path = 'data/packages.json'
    with open(output_path, 'w') as f:
        json.dump(unique_packages, f, indent=2)

    print(f"Saved {len(unique_packages)} packages to {output_path}")

    # Print category summary
    categories = {}
    for pkg in unique_packages:
        cat = pkg['category']
        categories[cat] = categories.get(cat, 0) + 1

    print("\nPackages by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")


if __name__ == '__main__':
    main()
