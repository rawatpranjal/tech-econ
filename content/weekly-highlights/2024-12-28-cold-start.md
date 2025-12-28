---
title: "Cold Start in Recommendations"
date: 2024-12-28
category: "Recommender Systems"
description: "How to bootstrap personalization when you have no data"
tags: ["Recommendations", "Cold Start", "LightFM", "Python", "Network Effects"]
draft: false
---

## The Problem

Every recommendation system faces an existential crisis at birth: how do you recommend anything when you know nothing about your users?

This is the **cold start problem**—one of the most fundamental challenges in personalization. It appears in three forms:

> **Three Types of Cold Start**
> - **New User:** A user with no interaction history
> - **New Item:** A product/content with no ratings yet
> - **New System:** A platform launching from scratch

Companies like Netflix, Spotify, and Amazon have each developed sophisticated solutions. The key insight from [Andrew Chen](https://a16z.com/author/andrew-chen/)'s research at Andreessen Horowitz: cold start isn't just a technical problem—it's a network effects problem.

In his book [*The Cold Start Problem*](https://www.coldstart.com/), Chen describes the "atomic network"—the smallest viable unit of users that makes a product useful. For recommendations, this means having enough data to find meaningful patterns.

## Common Approaches

### 1. Content-Based Bootstrapping

Use item features (genre, tags, description) to make initial recommendations without user history. This is how Spotify's "Discover Weekly" handles new users—it analyzes audio features like tempo, energy, and acousticness to find similar songs.

The advantage: you can recommend new items immediately based on their metadata. The downside: you miss the serendipity that comes from collaborative patterns.

### 2. Hybrid Models

Combine collaborative filtering with content features. **LightFM** is the go-to library for this approach:

> "LightFM can produce good results even for new users or items through its incorporation of side information."
> — [Maciej Kula](https://www.linkedin.com/in/maciejkula/), Lyst Engineering

The key innovation: LightFM learns embeddings for both users/items AND their features. When a new item arrives, it can immediately be placed in the embedding space based on its features.

### 3. Exploration Strategies

Use multi-armed bandits to actively learn preferences through controlled exploration. Netflix uses this for new profile onboarding—they show a diverse set of titles and use the ratings to quickly learn your taste.

The explore-exploit tradeoff: show what you think the user likes (exploit) vs. show something new to learn more (explore). Thompson Sampling and UCB are popular algorithms for this balance.

### 4. Transfer Learning

Use knowledge from related domains. If you know a user's music preferences, you might infer something about their podcast preferences. Spotify does this across their audio products.

## Try It Yourself

Here's a minimal example using LightFM with the MovieLens dataset. Install with `pip install lightfm`:

```python
from lightfm import LightFM
from lightfm.datasets import fetch_movielens
from lightfm.evaluation import precision_at_k

# Load data with item features (genre tags)
data = fetch_movielens(min_rating=4.0)

# Create hybrid model - 'warp' loss works well for implicit feedback
model = LightFM(loss='warp', no_components=64)

# Train on interactions + item features
# The item_features parameter is what enables cold-start!
model.fit(data['train'],
          item_features=data['item_features'],
          epochs=30,
          num_threads=4)

# Evaluate
train_precision = precision_at_k(model, data['train'], k=5).mean()
test_precision = precision_at_k(model, data['test'], k=5).mean()

print(f"Train Precision@5: {train_precision:.3f}")
print(f"Test Precision@5: {test_precision:.3f}")
```

**Key insight:** The `item_features` parameter is what enables cold-start recommendations. New items with known features (genres) can get recommendations immediately, even with zero ratings.

For new users, you can generate recommendations using only item features:

```python
import numpy as np

def recommend_for_new_user(model, item_features, n_items, top_k=10):
    """
    Generate recommendations for a brand new user.
    Uses only item features - no interaction history needed.
    """
    # Create a new user ID (doesn't exist in training data)
    new_user_id = 0

    # Score all items using just their features
    scores = model.predict(
        user_ids=new_user_id,
        item_ids=np.arange(n_items),
        item_features=item_features
    )

    # Return top-k items
    top_items = np.argsort(-scores)[:top_k]
    return top_items, scores[top_items]

# Get recommendations for a cold-start user
n_items = data['train'].shape[1]
recommendations, scores = recommend_for_new_user(
    model,
    data['item_features'],
    n_items,
    top_k=10
)

print("Top 10 recommendations for new user:")
for i, (item_id, score) in enumerate(zip(recommendations, scores)):
    print(f"  {i+1}. Item {item_id} (score: {score:.3f})")
```

## Real-World Applications

| Company | How They Solve Cold Start |
|---------|---------------------------|
| [Spotify](https://research.atspotify.com/publications/recommending-podcasts-for-cold-start-users-based-on-music-listening-and-taste/) | Uses audio features (tempo, energy, acousticness, danceability) to recommend songs to new users before learning their taste. Their "taste profiles" are built from 30-second listening segments. |
| [Amazon](https://www.amazon.science/publications/treating-cold-start-in-product-search-by-priors) | Leverages product categories, "customers also bought" patterns, and browse history to bootstrap recommendations. New products get initial visibility through category placement. |
| [Netflix](https://netflixtechblog.com/artwork-personalization-c589f074ad76) | Asks new users to rate ~10 titles during onboarding—a classic exploration strategy. They also use content features like cast, director, and genre for new releases. |
| [Uber Eats](https://www.uber.com/blog/uber-eats-recommending-marketplace/) | Uses location, time-of-day, and cuisine popularity to recommend restaurants before knowing individual preferences. Your first order strongly shapes future recommendations. |
| [TikTok](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you) | Their "interest graph" starts with your country and device. The first few videos are diverse; your engagement (watch time, not just likes) rapidly personalizes the feed. |
| [LinkedIn](https://engineering.linkedin.com/blog/2016/12/personalized-recommendations-in-linkedin-learning) | Uses your job title, company, and connections to recommend jobs and content. Professional signals provide strong cold-start features for B2B recommendations. |

## Further Reading

### Essential Reading
- [The Cold Start Problem](https://www.coldstart.com/) — Andrew Chen's definitive book on network effects and how startups overcome the chicken-and-egg problem
- [Metadata Embeddings for User and Item Cold-start Recommendations](https://arxiv.org/abs/1507.08439) — The original LightFM paper by Maciej Kula (2015)
- [Deep Neural Networks for YouTube Recommendations](https://research.google/pubs/deep-neural-networks-for-youtube-recommendations/) — How YouTube handles cold start at billion-user scale (RecSys 2016)

### Tools & Libraries
- [LightFM](https://making.lyst.com/lightfm/docs/home.html) — Hybrid matrix factorization with cold-start support
- [Surprise](https://surpriselib.com/) — scikit-learn style API for collaborative filtering
- [RecBole](https://github.com/RUCAIBox/RecBole) — 94 deep learning recommendation models in PyTorch
- [Microsoft Recommenders](https://github.com/recommenders-team/recommenders) — Production-quality examples and benchmarks

### Courses
- [Google ML Recommendation Course](https://developers.google.com/machine-learning/recommendation) — Free 4-hour course covering candidate generation through ranking
- [Fast.ai Lesson 7: Collaborative Filtering](https://course.fast.ai/Lessons/lesson7.html) — Jeremy Howard's intuitive deep dive into embeddings

### Key Researchers
- [Andrew Chen](https://a16z.com/author/andrew-chen/) — General Partner at a16z, author of The Cold Start Problem
- [Maciej Kula](https://www.linkedin.com/in/maciejkula/) — Creator of LightFM, previously ML at Lyst and Spotify

### Datasets for Practice
- [MovieLens](https://grouplens.org/datasets/movielens/) — Classic benchmark with 25M ratings and rich metadata
- [Netflix Prize](https://www.kaggle.com/datasets/netflix-inc/netflix-prize-data) — 100M+ anonymous movie ratings from 480k users
- [Amazon Reviews](https://cseweb.ucsd.edu/~jmcauley/datasets/amazon_v2/) — 233M reviews with product metadata across categories
