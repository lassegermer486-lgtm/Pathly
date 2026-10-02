"""
International online discovery (v1.3, Phase C).

Finds candidate institutions outside Germany whose study offer may be fully
online, from official datasets (ETER for Europe, IPEDS for the USA), and
writes them as normalized records next to the German ones:

    data/normalized/universities_intl.json

Discovery is not confirmation: every candidate starts with
online_de_status = review (registry.master.online_de).
"""
