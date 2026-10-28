import re


class HearingsFilter:
    """
    Marks hearings that are a substation expansion or a
    regional plan amendment.

    Returns the same records with a relevant flag.
    """

    HEARING = re.compile(
        r"öffentlich(?:e|en|er|es)?\s+auslegung"
        r"|offenlage"
        r"|öffentlichkeitsbeteiligung"
        r"|anhörung"
        r"|erörterung"
        r"|planfeststellung"
    )

    EQUIPMENT = re.compile(
        r"umspannwerk|umspannanlage|schaltanlage"
    )

    EXPANSION = re.compile(
        r"erweiterung|ersatzneubau|neubau|ausbau"
    )

    REGIONAL_PLAN = re.compile(
        r"regionalplanung|raumordnungsplan"
    )

    def apply(
        self,
        records: list[dict],
    ) -> list[dict]:

        for record in records:
            record["relevant"] = self._relevant(
                record
            )

        return records

    def _relevant(
        self,
        record: dict,
    ) -> bool:

        text = " ".join(
            str(record.get(key) or "")
            for key in ("title", "place_text")
        ).casefold()

        if self.HEARING.search(text) is None:
            return False

        if self.REGIONAL_PLAN.search(text):
            return True

        return (
            self.EQUIPMENT.search(text) is not None
            and self.EXPANSION.search(text) is not None
        )
