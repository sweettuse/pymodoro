from __future__ import annotations
from contextlib import suppress
from functools import lru_cache, partial
from typing import Optional

import keyring
import requests

key = keyring.get_password("linear", "auth")
tuse_id = keyring.get_password("linear", "tuse")

header = {"Content-Type": "application/json", "Authorization": key}
post = partial(requests.post, "https://api.linear.app/graphql", headers=header)


class IssueQuery:
    """query for the title of the issue in linear"""

    def __init__(self, issue_name):
        self.issue_name = issue_name.upper()

    def __hash__(self):
        return hash(self.issue_name)

    def __eq__(self, other):
        return self.issue_name == other.issue_name

    @property
    def json(self):
        return dict(query=self.query_str, operationName="Issue")

    @property
    def query_str(self):
        return """
            query Issue {
                issue(id: "issue_name") {
                    title
                }
            }
        """.replace(
            "issue_name", self.issue_name
        )

    @lru_cache
    def get(self) -> Optional[str]:
        res = post(json=self.json)
        with suppress(Exception):
            if res.ok:
                return res.json()["data"]["issue"]["title"]
