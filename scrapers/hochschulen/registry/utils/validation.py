def validate_university(university):
    errors = []

    if not university.get("name"):
        errors.append("missing_name")

    if university.get("country") != "DE":
        errors.append("invalid_country")

    if not university.get("state"):
        errors.append("missing_state")

    if not university.get("locations"):
        errors.append("missing_locations")

    return errors


def validate_registry(universities):
    invalid = []

    for university in universities:
        errors = validate_university(university)

        if errors:
            invalid.append({
                "name": university.get("name"),
                "errors": errors,
            })

    return invalid
