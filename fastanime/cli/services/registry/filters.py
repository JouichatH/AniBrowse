from typing import List

from ....libs.api.params import MediaSearchParams
from ....libs.api.types import MediaItem


class MediaFilter:
    """
    A class to filter, sort, and paginate a list of MediaItem objects
    based on ApiSearchParams.
    """

    # Mapping for season to month range (MMDD format)
    _SEASON_MONTH_RANGES = {
        "WINTER": (101, 331),  # Jan 1 - Mar 31
        "SPRING": (401, 630),  # Apr 1 - Jun 30
        "SUMMER": (701, 930),  # Jul 1 - Sep 30
        "FALL": (1001, 1231),  # Oct 1 - Dec 31
    }

    # Mapping for sort parameters to MediaItem attributes and order
    # (attribute_name, is_descending, is_nested_title_field)
    _SORT_MAPPING = {
        "ID": ("id", False, False),
        "ID_DESC": ("id", True, False),
        "POPULARITY": ("popularity", False, False),
        "POPULARITY_DESC": ("popularity", True, False),
        "SCORE": ("average_score", False, False),
        "SCORE_DESC": ("average_score", True, False),
        "TITLE_ROMAJI": ("romaji", False, True),  # Nested under title
        "TITLE_ROMAJI_DESC": ("romaji", True, True),
        "TITLE_ENGLISH": ("english", False, True),
        "TITLE_ENGLISH_DESC": ("english", True, True),
        "START_DATE": ("start_date", False, False),
        "START_DATE_DESC": ("start_date", True, False),
    }

    @classmethod
    def apply(
        cls, media_items: List[MediaItem], filters: MediaSearchParams
    ) -> List[MediaItem]:
        """
        Applies filtering, sorting, and pagination to a list of MediaItem objects.

        Args:
            media_items: The initial list of MediaItem objects to filter.
            params: An ApiSearchParams object containing the filter, sort, and pagination criteria.

        Returns:
            A new list of MediaItem objects, filtered, sorted, and paginated.
        """
        filtered_items = list(media_items)  # Create a mutable copy

        if filters.query:
            query_lower = filters.query.lower()
            filtered_items = [
                item
                for item in filtered_items
                if (
                    item.title
                    and (
                        (item.title.romaji and query_lower in item.title.romaji.lower())
                        or (
                            item.title.english
                            and query_lower in item.title.english.lower()
                        )
                        or (
                            item.title.native
                            and query_lower in item.title.native.lower()
                        )
                    )
                )
                or (item.description and query_lower in item.description.lower())
                or any(query_lower in syn.lower() for syn in item.synonymns)
            ]

        # IDs
        if filters.id_in:
            id_set = set(filters.id_in)
            filtered_items = [item for item in filtered_items if item.id in id_set]

        # Genres
        if filters.genre_in:
            genre_in_set = set(g.lower() for g in filters.genre_in)
            filtered_items = [
                item
                for item in filtered_items
                if any(g.lower() in genre_in_set for g in item.genres)
            ]
        if filters.genre_not_in:
            genre_not_in_set = set(g.lower() for g in filters.genre_not_in)
            filtered_items = [
                item
                for item in filtered_items
                if not any(g.lower() in genre_not_in_set for g in item.genres)
            ]

        # Tags
        if filters.tag_in:
            tag_in_set = set(t.lower() for t in filters.tag_in)
            filtered_items = [
                item
                for item in filtered_items
                if any(tag.name and tag.name.lower() in tag_in_set for tag in item.tags)
            ]
        if filters.tag_not_in:
            tag_not_in_set = set(t.lower() for t in filters.tag_not_in)
            filtered_items = [
                item
                for item in filtered_items
                if not any(
                    tag.name and tag.name.lower() in tag_not_in_set for tag in item.tags
                )
            ]

        # Status
        combined_status_in = set()
        if filters.status_in:
            combined_status_in.update(s.upper() for s in filters.status_in)
        if filters.status:
            combined_status_in.add(filters.status.upper())

        if combined_status_in:
            filtered_items = [
                item
                for item in filtered_items
                if item.status and item.status.upper() in combined_status_in
            ]
        if filters.status_not_in:
            status_not_in_set = set(s.upper() for s in filters.status_not_in)
            filtered_items = [
                item
                for item in filtered_items
                if item.status and item.status.upper() not in status_not_in_set
            ]

        # Popularity
        if filters.popularity_greater is not None:
            filtered_items = [
                item
                for item in filtered_items
                if item.popularity is not None
                and item.popularity > filters.popularity_greater
            ]
        if filters.popularity_lesser is not None:
            filtered_items = [
                item
                for item in filtered_items
                if item.popularity is not None
                and item.popularity < filters.popularity_lesser
            ]

        # Average Score
        if filters.averageScore_greater is not None:
            filtered_items = [
                item
                for item in filtered_items
                if item.average_score is not None
                and item.average_score > filters.averageScore_greater
            ]
        if filters.averageScore_lesser is not None:
            filtered_items = [
                item
                for item in filtered_items
                if item.average_score is not None
                and item.average_score < filters.averageScore_lesser
            ]

        # Date Filtering (combining season/year with startDate parameters)
        effective_start_date_greater = filters.startDate_greater
        effective_start_date_lesser = filters.startDate_lesser

        if filters.seasonYear is not None and filters.season is not None:
            season_range = cls._SEASON_MONTH_RANGES.get(filters.season.upper())
            if season_range:
                # Calculate start and end of the season in YYYYMMDD format
                season_start_date = filters.seasonYear * 10000 + season_range[0]
                season_end_date = filters.seasonYear * 10000 + season_range[1]

                # Combine with existing startDate_greater/lesser, taking the stricter boundary
                effective_start_date_greater = max(
                    effective_start_date_greater or 0, season_start_date
                )
                effective_start_date_lesser = min(
                    effective_start_date_lesser or 99999999, season_end_date
                )

        # TODO: re enable date filtering since date is a datetime

        # if filters.startDate is not None:
        #     # If a specific start date is given, it overrides ranges for exact match
        #     filtered_items = [
        #         item for item in filtered_items if item.start_date == filters.startDate
        #     ]
        # else:
        #     if effective_start_date_greater is not None:
        #         filtered_items = [
        #             item
        #             for item in filtered_items
        #             if item.start_date is not None
        #             and item.start_date >= datetime(y,m,d)
        #         ]
        #     if effective_start_date_lesser is not None:
        #         filtered_items = [
        #             item
        #             for item in filtered_items
        #             if item.start_date is not None
        #             and item.start_date <= effective_start_date_lesser
        #         ]

        # if filters.endDate_greater is not None:
        #     filtered_items = [
        #         item
        #         for item in filtered_items
        #         if item.end_date is not None
        #         and item.end_date >= filters.endDate_greater
        #     ]
        # if filters.endDate_lesser is not None:
        #     filtered_items = [
        #         item
        #         for item in filtered_items
        #         if item.end_date is not None and item.end_date <= filters.endDate_lesser
        #     ]

        # Format and Type
        if filters.format_in:
            format_in_set = set(f.upper() for f in filters.format_in)
            filtered_items = [
                item
                for item in filtered_items
                if item.format and item.format.upper() in format_in_set
            ]
        if filters.type:
            filtered_items = [
                item
                for item in filtered_items
                if item.type and item.type.upper() == filters.type.upper()
            ]

        # --- 2. Apply Sorting ---
        if filters.sort:
            sort_criteria = (
                [filters.sort] if isinstance(filters.sort, str) else filters.sort
            )

            # Sort in reverse order of criteria so the first criterion is primary
            for sort_param in reversed(sort_criteria):
                sort_info = cls._SORT_MAPPING.get(sort_param.upper())
                if sort_info:
                    attr_name, is_descending, is_nested_title = sort_info

                    def sort_key(item: MediaItem):
                        if is_nested_title:
                            # Handle nested title attributes
                            title_obj = item.title
                            if title_obj and hasattr(title_obj, attr_name):
                                val = getattr(title_obj, attr_name)
                                return val.lower() if isinstance(val, str) else val
                            return None  # Handle missing title or attribute gracefully
                        else:
                            # Handle direct attributes
                            return getattr(item, attr_name)

                    # Sort, handling None values (None typically sorts first in ascending)
                    filtered_items.sort(
                        key=lambda item: (sort_key(item) is None, sort_key(item)),
                        reverse=is_descending,
                    )
                else:
                    print(f"Warning: Unknown sort parameter '{sort_param}'. Skipping.")

        # --- 3. Apply Pagination ---
        start_index = (filters.page - 1) * filters.per_page
        end_index = start_index + filters.per_page
        paginated_items = filtered_items[start_index:end_index]

        return paginated_items
