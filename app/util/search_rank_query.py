from sqlalchemy import case, func, or_
def build_search_rank(model, raw_query: str, normalized_query: str):
    raw_q = raw_query.lower()
    norm_q = normalized_query.lower()

    lower_name = func.lower(model.name)
    lower_norm_name = func.lower(model.normalized_name)

    combo_penalty = case(
        (
            or_(
                lower_name.contains(" and "),
                lower_name.contains("/"),
                lower_name.contains(" tablet"),
                lower_name.contains(" tablets"),
                lower_name.contains(" capsule"),
                lower_name.contains(" capsules"),
                lower_name.contains(" chewable"),
                lower_name.contains(" solution"),
                lower_name.contains(" injection"),
                lower_name.contains(" mg"),
                lower_name.contains(" ml"),
            ),
            10,
        ),
        else_=0,
    )

    kind_bonus = case(
        (func.lower(model.kind) == "generic", 4),
        else_=0,
    )

    return (
        case((lower_name == raw_q, 100), else_=0) +
        case((lower_norm_name == norm_q, 95), else_=0) +
        case((lower_name.startswith(raw_q), 80), else_=0) +
        case((lower_norm_name.startswith(norm_q), 75), else_=0) +
        case((lower_name.contains(raw_q), 60), else_=0) +
        case((lower_norm_name.contains(norm_q), 55), else_=0) +
        kind_bonus -
        combo_penalty
    )