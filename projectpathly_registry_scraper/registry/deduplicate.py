from .normalize import domain_key, university_name_key

def deduplicate(universities):
    result = []
    seen_domains = {}
    seen_names = {}

    for uni in universities:
        dkey = domain_key(uni.official_url)
        nkey = university_name_key(uni.name)

        existing = seen_domains.get(dkey) if dkey else None
        if existing is None:
            existing = seen_names.get(nkey)

        if existing is not None:
            # Keep all unique locations from duplicate observations.
            known = {(x.street, x.postal_code, x.city, x.name) for x in existing.locations}
            for loc in uni.locations:
                k = (loc.street, loc.postal_code, loc.city, loc.name)
                if k not in known:
                    existing.locations.append(loc)
            continue

        result.append(uni)
        if dkey:
            seen_domains[dkey] = uni
        seen_names[nkey] = uni

    return result
