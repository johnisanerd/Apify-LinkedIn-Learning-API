"""LinkedIn Learning API: example client.

Searches the public LinkedIn Learning course catalog by keyword, skill level,
length or software, and pulls the full record for any course URL: rating,
written learner reviews, the complete syllabus with a free-preview flag on
every lesson, instructors with profile links, skills and certificate details.
Everything comes from the pages LinkedIn Learning already publishes to
logged-out visitors, so there is no login, no cookie and no site license.

Get a free Apify API token: https://apify.com?fpr=9n7kx3
Actor: https://apify.com/johnvc/linkedin-learning-api?fpr=9n7kx3
Input schema: https://apify.com/johnvc/linkedin-learning-api/input-schema?fpr=9n7kx3

Run it:
    uv sync
    cp .env.example .env      # then paste your token into .env
    uv run python linkedin-learning-api-example.py

Pick one example:
    uv run python linkedin-learning-api-example.py --example default
    uv run python linkedin-learning-api-example.py --example catalog
    uv run python linkedin-learning-api-example.py --example reviews
    uv run python linkedin-learning-api-example.py --example new-courses
    uv run python linkedin-learning-api-example.py --example all
"""

import argparse
import json
import os
import sys

from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

ACTOR_ID = "johnvc/linkedin-learning-api"

# Every run below asks for a small number of rows on purpose. You pay per row
# delivered ($0.10 per 1,000 search results, $0.50 per 1,000 full course
# records), so keep the first run cheap, confirm the shape of the data, then
# raise maxItems once you know it is what you want.
SMALL = 5


def client() -> ApifyClient:
    token = os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")
    if not token or token in ("your_apify_api_token_here", "paste_your_real_token_here"):
        sys.exit(
            "Set APIFY_API_TOKEN first: copy .env.example to .env and paste your token, "
            "or export APIFY_API_TOKEN in your shell.\n"
            "Get one free: https://apify.com?fpr=9n7kx3"
        )
    return ApifyClient(token)


def rows(api: ApifyClient, run_input: dict, limit: int = SMALL) -> list[dict]:
    """Run the Actor and return the first rows of its dataset.

    apify-client 3.x returns a typed Run object here, not a dict, so the
    dataset id is an attribute. On 2.x this was run["defaultDatasetId"].
    """
    run = api.actor(ACTOR_ID).call(run_input=run_input)
    if run is None:
        sys.exit("The Actor run did not return a result.")
    return list(api.dataset(run.default_dataset_id).iterate_items(limit=limit))


def names(people: list | None) -> str:
    """Instructor names as one comma-separated string."""
    return ", ".join(p.get("name", "") for p in (people or [])) or "instructor not listed"


def print_search_row(row: dict) -> None:
    """Print one search_result row. Handles no_results and error rows too."""
    kind = row.get("resultType")
    if kind == "no_results":
        print(f"  no match: {row.get('message')}")
        return
    if kind == "error":
        # An invalid-input error names no URL, so only append one when present.
        where = row.get("sourceUrl")
        print(f"  error: {row.get('errorMessage')}" + (f" ({where})" if where else ""))
        return
    print(f"\n{row.get('position')}. {row.get('title')}  [{row.get('entityType')}]")
    print(f"  by {names(row.get('instructors'))}")
    print(f"  {row.get('durationText')} | {row.get('viewersText')} | {row.get('releaseText')}")
    print(f"  {row.get('courseUrl')}")


def run_default(api: ApifyClient) -> None:
    """Cheap general quick-start: one keyword search, five rows.

    Shows the search-mode filters without raising the cost. Every value here
    comes from the Actor's input schema; sortBy, difficultyLevel and duration
    are left at their wide defaults; entityType is set to COURSE so the five
    rows are all full courses rather than single videos or paths.
    """
    print("\n=== Search: python courses (default cheap run) ===")
    # Inputs are kept small (one query, maxItems=5) to keep this first run
    # inexpensive: five search rows cost about $0.0005, plus Apify's platform
    # accounting events of $0.00001 per run start and per stored row. Raise
    # maxItems once you have your own API token and know your budget.
    results = rows(api, {
        "mode": "search",
        "queries": ["python"],
        "sortBy": "RELEVANCE",
        "difficultyLevel": "ANY",
        "entityType": "COURSE",
        "duration": "ANY",
        "maxItems": SMALL,
    })
    print(f"Returned {len(results)} row(s).")
    for row in results:
        print_search_row(row)
    if results and results[0].get("approximateTotalResults"):
        print(f"\nLinkedIn reports about {results[0]['approximateTotalResults']:,} matches "
              f"for '{results[0].get('searchQuery')}'.")


def run_course_catalog_export(api: ApifyClient) -> None:
    """Course catalog rows as JSON, no login.

    Mirrors the "LinkedIn Learning Course Data as JSON, No Login" task:
    https://apify.com/johnvc/linkedin-learning-api/examples/linkedin-learning-course-data-json?fpr=9n7kx3

    Same shape as the published task (search mode, one query) with maxItems
    clamped from 25 to 5 for a cheap first run. Each row is printed as JSON
    so you can see every field name, including thumbnailUrl. To build a
    fuller course catalog, raise maxItems and set expandWithFilters to true,
    which is the only way past LinkedIn's 50-results-per-query ceiling.
    """
    print("\n=== Course catalog as JSON: project management ===")
    results = rows(api, {
        "mode": "search",
        "queries": ["project management"],
        "maxItems": SMALL,
    })
    for row in results:
        if row.get("resultType") != "search_result":
            print_search_row(row)
            continue
        print(json.dumps(row, indent=2))


def run_course_reviews(api: ApifyClient) -> None:
    """Written learner reviews and ratings for one course.

    Mirrors the "Extract LinkedIn Learning Course Reviews and Ratings" task:
    https://apify.com/johnvc/linkedin-learning-api/examples/extract-linkedin-learning-course-reviews?fpr=9n7kx3

    Details mode on one real course URL from that task (it uses three). One
    full course record costs about $0.0005 (plus Apify's platform accounting
    events of $0.00001 per run start and per stored row) and carries
    ratingValue, ratingCount, enrollmentCount, reviews, tableOfContents, skills
    and certificate fields.
    """
    print("\n=== Course reviews: Python Essential Training ===")
    results = rows(api, {
        "mode": "details",
        "courseUrls": ["https://www.linkedin.com/learning/python-essential-training-18764650"],
    }, limit=1)
    for course in results:
        if course.get("resultType") != "course_detail":
            print_search_row(course)
            continue
        print(f"{course.get('title')}  ({course.get('difficultyLevel')}, {course.get('language')})")
        # ratingCount and enrollmentCount are absent on a course with no
        # ratings, and freeLessonCount is absent when no lesson is free (the
        # Actor drops empty fields), so guard them all before formatting.
        rating_count = course.get("ratingCount") or 0
        learners = course.get("enrollmentCount") or 0
        print(f"  rating {course.get('ratingValue')} from {rating_count:,} ratings, "
              f"{learners:,} learners")
        print(f"  {course.get('lessonCount') or 0} lessons, {course.get('freeLessonCount') or 0} free to watch, "
              f"certificate: {course.get('hasCertificate')}")
        print(f"  skills: {', '.join(s.get('name', '') for s in course.get('skills') or [])}")
        reviews = course.get("reviews") or []
        print(f"  {len(reviews)} written review(s) on the page:")
        for review in reviews[:3]:
            print(f"    {review.get('rating')}/5  {review.get('authorName')} "
                  f"({review.get('authorJobTitle') or 'no title'})")
            print(f"      {(review.get('body') or '')[:160].strip()}")


def run_track_new_courses(api: ApifyClient) -> None:
    """Newest courses on a topic, release date first.

    Mirrors the "Track New LinkedIn Learning Course Releases" task:
    https://apify.com/johnvc/linkedin-learning-api/examples/track-new-linkedin-learning-courses?fpr=9n7kx3

    Same shape as the published task (search mode, sortBy RECENCY) with
    maxItems clamped from 25 to 5. Save this input as a Task in the Apify
    Console and schedule it weekly to watch a topic for new releases.
    """
    print("\n=== New releases: artificial intelligence, newest first ===")
    results = rows(api, {
        "mode": "search",
        "queries": ["artificial intelligence"],
        "sortBy": "RECENCY",
        "maxItems": SMALL,
    })
    for row in results:
        if row.get("resultType") != "search_result":
            print_search_row(row)
            continue
        print(f"{row.get('releaseText') or '':<24} {(row.get('title') or '')[:60]:<62} "
              f"{names(row.get('instructors'))[:30]}")


EXAMPLES = {
    "default": run_default,
    "catalog": run_course_catalog_export,
    "reviews": run_course_reviews,
    "new-courses": run_track_new_courses,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="LinkedIn Learning API examples")
    parser.add_argument("--example", choices=[*EXAMPLES, "all"], default="default",
                        help="Which example to run (default: default)")
    args = parser.parse_args()

    api = client()
    chosen = list(EXAMPLES) if args.example == "all" else [args.example]
    for name in chosen:
        EXAMPLES[name](api)


if __name__ == "__main__":
    main()
