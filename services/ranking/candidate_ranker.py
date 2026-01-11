from typing import Optional


data = {
    "visual": "The examination of Jane Armstrong of the County of Dunnigall beinge Sworne -- examined before Vs Henry Finch Esquire Major of the Citty of Londonderry and George Carew Justice of the Peace by Authoryty of Parliment for the Prouince of Vlster, 23 Aprill 1653 Sworned -- examined sayeth. In the yeare 1641 there came to her husbands house in the morning Edmond oge Oneale -- Neale oge Oneale, the Sayd Neale O Neale came Caulled William Betty her husband to Come forth to him shee was vnwilling hee should goe be reason shee sawe that Edmond Oneale was there whom shee Knew to be a blody man, but her husband haueing Some hopes that Neale O Neale would not See him receaue hurt cam forth, -- Edmond O Neale Commanded his men to Kill him who flocked aboute him -- one with a peese went to shoote him -- the examinent went between to saue her husband, -- they did not shoote him but Cutt him downe with Swords -- afterwards Came rune after his sonne William Betty who came rune away when they were Killing his father -- Killed him -- Killd Dauid Long stripped the examinent -- Seuerall other -- Commanded his men to hange her if shee would not Confes her mony but by the perswasions of Sume and Gods mercy shee escaped -- no farther Sayeth. Henry Finch",
    "normalized": "The examination of Jane Armstrong of the County of Donegal being Sworn -- examined before Vs Henry Finch Esquire Major of the Citty of Londonderry and George Carew Justice of the Peace by Authoryty of Parliment for the Province of Ulster, 23 Aprill 1653 Sworned -- examined sayeth. In the year 1641 there came to her husbands house in the morning Edmond oge Oneale -- Neale oge Oneale, the Said Neale O Neale came Caulled William Betty her husband to Come forth to him shee was unwilling he should goe be reason shee saw that Edmond Oneale was there whom shee Knew to be a blody man, but her husband having Some hopes that Neale O Neale would not See him receaue hurt cam forth, -- Edmond O Neale Commanded his men to Kill him who flocked about him -- one with a pees went to shoot him -- the examinent went between to save her husband, -- they did not shoot him but Cutt him down with Swords -- afterwards Came run after his sonne William Betty who came run away when they were Killing his father -- Killed him -- Killd David Long stripped the examinent -- Severall other -- Commanded his men to hang her if shee would not Confs her moni but by the perswasions of Sum and Gods mercy shee escaped -- no farther Sayeth. Henry Finch",
    "ents": [
        {
            "entity_meta_data": {
                "text": "Jane Armstrong",
                "label": "PER",
                "score": 0.9999856352806091,
                "start": 19,
                "end": 33,
            },
            "candidate_entities": [
                {
                    "person": "https://kg.virtualtreasury.ie/person/Armstrong_Jane_c17/v12pgt5",
                    "label": "Armstrong_Jane",
                    "entityCard": "https://vrti-graph.adaptcentre.ie/entity-card/person/Armstrong_Jane_c17/v12pgt5",
                    "idNodes": "https://kg.virtualtreasury.ie/normalised-appellation-surname-forename/Armstrong_Jane | https://kg.virtualtreasury.ie/normalized-appellation-forename/Jane | https://kg.virtualtreasury.ie/normalized-appellation-surname/Armstrong | https://kg.virtualtreasury.ie/vrti-identifier/v12pgt5",
                    "idLabels": ["Armstrong", " Jane Armstrong", "Jane", "v12pgt5"],
                    "identifierCount": "4",
                    "genders": ["Female"],
                    "eras": ["Early-Modern-1500-1749"],
                    "residences": "https://kg.virtualtreasury.ie/place/present-day/county/Donegal/v14g1sb",
                    "residencesLabels": ["Donegal", "Dún na nGall"],
                    "documentSources": "https://1641.tcd.ie/",
                    "events": "https://kg.virtualtreasury.ie/floruit/Armstrong_Jane_c17/v12pgt5",
                    "eventCount": "1",
                },
                {
                    "person": "https://kg.virtualtreasury.ie/person/Armstrong_Jane_c17/v1g74tz",
                    "label": "Armstrong_Jane",
                    "entityCard": "https://vrti-graph.adaptcentre.ie/entity-card/person/Armstrong_Jane_c17/v1g74tz",
                    "idNodes": "https://kg.virtualtreasury.ie/normalised-appellation-surname-forename/Armstrong_Jane | https://kg.virtualtreasury.ie/normalized-appellation-forename/Jane | https://kg.virtualtreasury.ie/normalized-appellation-surname/Armstrong | https://kg.virtualtreasury.ie/vrti-identifier/v1g74tz",
                    "idLabels": ["Armstrong", " Jane Armstrong", "Jane", "v1g74tz"],
                    "identifierCount": "4",
                    "genders": ["Female"],
                    "eras": ["Early-Modern-1500-1749"],
                    "residences": "https://kg.virtualtreasury.ie/place/present-day/city/Belfast/v1sw3d3",
                    "residencesLabels": ["Belfast", "Béal Feirste"],
                    "documentSources": "https://1641.tcd.ie/",
                    "events": "https://kg.virtualtreasury.ie/floruit/Armstrong_Jane_c17/v1g74tz",
                    "eventCount": "1",
                },
            ],
        },
        {
            "entity_meta_data": {
                "text": "Donegal",
                "label": "LOC",
                "score": 0.9997882843017578,
                "start": 51,
                "end": 58,
            },
            "candidate_entities": [
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/townland/Donegal/v1mjf98",
                    "era": "present-day",
                    "english": "Donegal",
                    "irish": "Dún na nGall",
                    "types": ["PresentDayTownland"],
                    "parentPlace": [
                        {
                            "Donegal": "https://kg.virtualtreasury.ie/place/present-day/parish/Donegal/v19gx9f"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/county/Donegal/v14g1sb",
                    "era": "present-day",
                    "english": "Donegal",
                    "irish": "Dún na nGall",
                    "types": ["PresentDayCounty"],
                    "parentPlace": [
                        {
                            "Ulster": "https://kg.virtualtreasury.ie/place/present-day/province/Ulster/v1gsn33"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/townland/Donegall-West/v12z1rx",
                    "era": "present-day",
                    "english": "Donegall West",
                    "irish": "Dún na nGall Thiar",
                    "types": ["PresentDayTownland"],
                    "parentPlace": "",
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/poor-law-union/Donegal/v12vk8c",
                    "era": "modern-1750-1922",
                    "english": "Donegal",
                    "irish": "",
                    "types": ["Modern-1750-1922-Poor-Law-Union", "Poor-Law-Union"],
                    "parentPlace": "",
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/county/Donegal/2295",
                    "era": "modern-1750-1922",
                    "english": "Donegal",
                    "irish": "",
                    "types": ["County", "Modern-1750-1922", "Modern-1750-1922-County"],
                    "parentPlace": [
                        {
                            "Ulster": "https://kg.virtualtreasury.ie/place/modern-1750-1922/province/Ulster/2308"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/town/Donegal/v16v9qq",
                    "era": "present-day",
                    "english": "Donegal",
                    "irish": "Dún na nGall",
                    "types": ["PresentDayTown"],
                    "parentPlace": [
                        {"place": "http://data.logainm.ie/place/1372456 "},
                        {"place": " http://data.logainm.ie/place/54"},
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/county/Donegal/v1x6s8j",
                    "era": "modern-1750-1922",
                    "english": "Donegal",
                    "irish": "",
                    "types": ["County", "Modern-1750-1922", "Modern-1750-1922-County"],
                    "parentPlace": [
                        {
                            "Ulster": "https://kg.virtualtreasury.ie/place/modern-1750-1922/province/Ulster/v1z2s3p"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/townland/Donegall/v11fzz9",
                    "era": "present-day",
                    "english": "Donegall",
                    "irish": "",
                    "types": ["PresentDayTownland"],
                    "parentPlace": [
                        {
                            "Devenish": "https://kg.virtualtreasury.ie/place/present-day/parish/Devenish/v13y6fq"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/townland/Donegall-East/v19kv3s",
                    "era": "present-day",
                    "english": "Donegall East",
                    "irish": "Dún na nGall Thoir",
                    "types": ["PresentDayTownland"],
                    "parentPlace": "",
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/townland/Donegal/v1d55gk",
                    "era": "present-day",
                    "english": "Donegal",
                    "irish": "Dún na nGall",
                    "types": ["PresentDayTownland"],
                    "parentPlace": [
                        {
                            "Knockgraffon": "https://kg.virtualtreasury.ie/place/present-day/parish/Knockgraffon/v1v91rm"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/townland/Donegal/v16f8xb",
                    "era": "present-day",
                    "english": "Donegal",
                    "irish": "Dún na nGall",
                    "types": ["PresentDayTownland"],
                    "parentPlace": [
                        {
                            "Clonmel": "https://kg.virtualtreasury.ie/place/present-day/parish/Clonmel/v1br6q3"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/early-modern-1500-1749/county/Donegal/v1qf2y7",
                    "era": "early-modern-1500-1749",
                    "english": "Donegal",
                    "irish": "",
                    "types": ["County", "EarlyModernCounty"],
                    "parentPlace": "",
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/county/Donegal/v17nzz9",
                    "era": "modern-1750-1922",
                    "english": "Donegal",
                    "irish": "",
                    "types": ["County", "Modern-1750-1922", "Modern-1750-1922-County"],
                    "parentPlace": [
                        {
                            "Ulster": "https://kg.virtualtreasury.ie/place/modern-1750-1922/province/Ulster/v1zh23z"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/parish/Donegal/v19gx9f",
                    "era": "present-day",
                    "english": "Donegal",
                    "irish": "Dún na nGall",
                    "types": ["PresentDayParish"],
                    "parentPlace": [
                        {
                            "Tirhugh": "https://kg.virtualtreasury.ie/place/present-day/barony/Tirhugh/v1t1ms3"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/townland/Donegall-Middle/v1mff66",
                    "era": "present-day",
                    "english": "Donegall Middle",
                    "irish": "Dún na nGall Láir",
                    "types": ["PresentDayTownland"],
                    "parentPlace": "",
                },
            ],
        },
        {
            "entity_meta_data": {
                "text": "Londonderry",
                "label": "LOC",
                "score": 0.9285251498222351,
                "start": 135,
                "end": 146,
            },
            "candidate_entities": [
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/city/Londonderry/v15c7bs",
                    "era": "modern-1750-1922",
                    "english": "Londonderry",
                    "irish": "",
                    "types": ["City", "Modern-1750-1922", "Modern-1750-1922-City"],
                    "parentPlace": [
                        {
                            "Londonderry": "https://kg.virtualtreasury.ie/place/modern-1750-1922/county/Londonderry/v1h96px"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/barony/North-West-Liberties-of-Londonderry/v1x6bk6",
                    "era": "present-day",
                    "english": "North-West Liberties of Londonderry",
                    "irish": "Líbeartaí Thiar Thuaidh Dhoire",
                    "types": ["PresentDayBarony"],
                    "parentPlace": [
                        {
                            "Londonderry": "https://kg.virtualtreasury.ie/place/present-day/county/Londonderry/v1v2r9j"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/city/Londonderry/v1mz36b",
                    "era": "modern-1750-1922",
                    "english": "Londonderry",
                    "irish": "",
                    "types": ["City", "Modern-1750-1922", "Modern-1750-1922-City"],
                    "parentPlace": [
                        {
                            "Londonderry": "https://kg.virtualtreasury.ie/place/modern-1750-1922/county/Londonderry/v1t1t1g"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/parish/Londonderry_City/v1v4r2d",
                    "era": "modern-1750-1922",
                    "english": "Londonderry City",
                    "irish": "",
                    "types": ["Modern-1750-1922", "Modern-1750-1922-Parish", "Parish"],
                    "parentPlace": "",
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/poor-law-union/Londonderry/v1nq58h",
                    "era": "modern-1750-1922",
                    "english": "Londonderry",
                    "irish": "",
                    "types": ["Modern-1750-1922-Poor-Law-Union", "Poor-Law-Union"],
                    "parentPlace": "",
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/county/Londonderry/v1h96px",
                    "era": "modern-1750-1922",
                    "english": "Londonderry",
                    "irish": "",
                    "types": ["County", "Modern-1750-1922", "Modern-1750-1922-County"],
                    "parentPlace": [
                        {
                            "Ulster": "https://kg.virtualtreasury.ie/place/modern-1750-1922/province/Ulster/v1zh23z"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/townland/Londonderry/v1zc5h6",
                    "era": "present-day",
                    "english": "Londonderry",
                    "irish": "Doire",
                    "types": ["PresentDayTownland"],
                    "parentPlace": [
                        {
                            "Templemore": "https://kg.virtualtreasury.ie/place/present-day/parish/Templemore/v19rx6d"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/early-modern-1500-1749/townland/The-Towne-of-Londonderry/v1jty53",
                    "era": "early-modern-1500-1749",
                    "english": "The Towne of Londonderry",
                    "irish": "",
                    "types": ["EarlyModernTownland", "Townland"],
                    "parentPlace": [
                        {
                            "Derry": "https://kb.virtualtreasury.ie/place/early-modern-1500-1749/county/Derry/v12j6fy "
                        },
                        {
                            "Derry": " https://kg.virtualtreasury.ie/place/early-modern-1500-1749/county/Derry/v12j6fy"
                        },
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/county/Londonderry/v1t1t1g",
                    "era": "modern-1750-1922",
                    "english": "Londonderry",
                    "irish": "",
                    "types": ["County", "Modern-1750-1922", "Modern-1750-1922-County"],
                    "parentPlace": [
                        {
                            "Ulster": "https://kg.virtualtreasury.ie/place/modern-1750-1922/province/Ulster/v1z2s3p"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/parish/Londonderry_City/2021",
                    "era": "modern-1750-1922",
                    "english": "Londonderry City",
                    "irish": "",
                    "types": ["Modern-1750-1922", "Modern-1750-1922-Parish", "Parish"],
                    "parentPlace": "",
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/county/Londonderry/v1v2r9j",
                    "era": "present-day",
                    "english": "Londonderry",
                    "irish": "Doire",
                    "types": ["PresentDayCounty"],
                    "parentPlace": [
                        {
                            "Ulster": "https://kg.virtualtreasury.ie/place/present-day/province/Ulster/v1gsn33"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/city/Londonderry/2124",
                    "era": "modern-1750-1922",
                    "english": "Londonderry",
                    "irish": "",
                    "types": ["City", "Modern-1750-1922", "Modern-1750-1922-City"],
                    "parentPlace": [
                        {
                            "Londonderry": "https://kg.virtualtreasury.ie/place/modern-1750-1922/county/Londonderry/2298"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/parish/Londonderry_City/v17mdj1",
                    "era": "modern-1750-1922",
                    "english": "Londonderry City",
                    "irish": "",
                    "types": ["Modern-1750-1922", "Modern-1750-1922-Parish", "Parish"],
                    "parentPlace": "",
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/county/Londonderry/v1v2r9j",
                    "era": "present-day",
                    "english": "Derry",
                    "irish": "Doire",
                    "types": ["PresentDayCounty"],
                    "parentPlace": [
                        {
                            "Ulster": "https://kg.virtualtreasury.ie/place/present-day/province/Ulster/v1gsn33"
                        }
                    ],
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/county/Londonderry/2298",
                    "era": "modern-1750-1922",
                    "english": "Londonderry",
                    "irish": "",
                    "types": ["County", "Modern-1750-1922", "Modern-1750-1922-County"],
                    "parentPlace": [
                        {
                            "Ulster": "https://kg.virtualtreasury.ie/place/modern-1750-1922/province/Ulster/2308"
                        }
                    ],
                },
            ],
        },
        {
            "entity_meta_data": {
                "text": "George Carew",
                "label": "PER",
                "score": 0.9999857544898987,
                "start": 151,
                "end": 163,
            },
            "candidate_entities": [
                {
                    "person": "https://kg.virtualtreasury.ie/person/Carew_George_c17/v1yh3v3",
                    "label": "Carew_George_c17",
                    "entityCard": "https://vrti-graph.adaptcentre.ie/entity-card/person/Carew_George_c17/v1yh3v3",
                    "idNodes": "https://kg.virtualtreasury.ie/normalized-appellation-forename/George | https://kg.virtualtreasury.ie/normalized-appellation-surname-forename/Carew_George | https://kg.virtualtreasury.ie/normalized-appellation-surname/Carew",
                    "idLabels": ["Carew", " George Carew", "George"],
                    "identifierCount": "3",
                    "genders": ["Male"],
                    "eras": ["Early-Modern-1500-1749"],
                    "residences": "",
                    "residencesLabels": [""],
                    "documentSources": "",
                    "events": "",
                    "eventCount": "0",
                }
            ],
        },
        {
            "entity_meta_data": {
                "text": "Ulster",
                "label": "LOC",
                "score": 0.9802047610282898,
                "start": 231,
                "end": 237,
            },
            "candidate_entities": [
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/province/Ulster/v1z2s3p",
                    "era": "modern-1750-1922",
                    "english": "Ulster",
                    "irish": "",
                    "types": [
                        "Modern-1750-1922",
                        "Modern-1750-1922-Province",
                        "Province",
                    ],
                    "parentPlace": "",
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/province/Ulster/2308",
                    "era": "modern-1750-1922",
                    "english": "Ulster",
                    "irish": "",
                    "types": [
                        "Modern-1750-1922",
                        "Modern-1750-1922-Province",
                        "Province",
                    ],
                    "parentPlace": "",
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/province/Ulster/v1gsn33",
                    "era": "present-day",
                    "english": "Ulster",
                    "irish": "Chúige Uladh",
                    "types": ["PresentDayProvince", "Province"],
                    "parentPlace": "",
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/present-day/province/Ulster/v1gsn33",
                    "era": "present-day",
                    "english": "Ulster",
                    "irish": "Cúige Uladh",
                    "types": ["PresentDayProvince", "Province"],
                    "parentPlace": "",
                },
                {
                    "place": "https://kg.virtualtreasury.ie/place/modern-1750-1922/province/Ulster/v1zh23z",
                    "era": "modern-1750-1922",
                    "english": "Ulster",
                    "irish": "",
                    "types": [
                        "Modern-1750-1922",
                        "Modern-1750-1922-Province",
                        "Province",
                    ],
                    "parentPlace": "",
                },
            ],
        },
    ],
}


class Eras:
    EARLY_MODERN = "early-modern-1500-1749"
    MODERN = "modern-1750-1922"
    PRESENT_DAY = "present-day"

    ERA_RANGES = {
        EARLY_MODERN: (1500, 1749),
        MODERN: (1750, 1922),
        PRESENT_DAY: (1923, 2100),  # Bit of extra padding incase this does amazing
    }
    ALL_ERAS = [EARLY_MODERN, MODERN, PRESENT_DAY]

    @classmethod
    def get_doc_era(cls, year: int):
        for era, (start, end) in cls.ERA_RANGES.items():
            if start <= year <= end:
                return era
        return None


class CandidateRanker:

    def __init__(self, data: dict, document_year: Optional[int] = None):
        self.data = data
        self.entities = data["ents"]
        self.raw_text = data["visual"]
        self.normalised_text = data["normalized"]
        self.document_year = document_year
        self.document_era = "early-modern-1500-1749"

    def rank(self, top_k=5):
        """Function to rank the top 5 entites if applicable"""
        print("in rank")
        rank_results = {}
        for entity in self.entities:
            entity_mention = entity["entity_meta_data"]["text"]
            rank = self.rank_entity_mention(entity, top_k)
            rank_results[entity_mention] = rank
        return rank_results

    def rank_entity_mention(self, entity, top_k: int = 5):
        mention = entity["entity_meta_data"]["text"]
        label = entity["entity_meta_data"]["label"]
        candidates = entity.get("candidate_entities", [])

        if not candidates:
            return []

        scored_mentions = []
        for candidate in candidates:
            score = self.score_candidate(mention, candidate, label)

            scored_mentions.append(
                {
                    "candidate": candidate,
                    "score": score,
                    "mention": mention,
                    "ner_label": label,
                    "confidence": self.get_confidence_level(score),
                }
            )

        scored_mentions.sort(key=lambda x: x["score"], reverse=True)
        return scored_mentions[:top_k]

    def score_candidate(self, mention, candidate, label):
        """Calculate the score for a candidate"""
        era_score = self.get_era_score(candidate, label)
        return era_score

    def get_era_score(self, candidate, label):

        if not self.document_era:
            return 0.5

        if label == "PER":
            return self.check_person_era(candidate)
        elif label == "LOC":
            return self.check_location_score(candidate)
        return 0.5

    def check_person_era(self, candidate):
        candidate_eras = candidate.get("eras", [])
        if not candidate_eras:
            return 0.5  # Return half if no era info
        for era in candidate_eras:
            if era.lower() == self.document_era:
                print("The same")
                return 1.0
        return 0.0

    def check_location_score(self, candidate):
        candidate_eras = candidate.get("era", "")
        if not candidate_eras:
            return 0.5

        if candidate_eras.lower() == self.document_era.lower():
            return 1.0

        return 0.0

    def get_confidence_level(self, score):
        if score > 0.75:
            return "High confidence"
        elif score >= 0.5:
            return "Medium Confidence"
        else:
            return "Low confidence"


cr = CandidateRanker(data)
x = cr.rank(top_k=5)
print(x)
