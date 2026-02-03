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
