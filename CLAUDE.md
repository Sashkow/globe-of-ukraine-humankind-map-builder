# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

"Globe of Ukraine" - a Humankind map implementing the classic Ukrainian joke (Ukraine as the entire world). Built for multiplayer with friends from different Ukrainian regions. The map should be based on real geography (SRTM elevation, actual raion boundaries, real rivers) but features can be exaggerated to improve visual appeal or gameplay. Priority: start geographically accurate, then adjust to make Ukrainian landmarks more prominent and city placement more strategic.

## Commands

```bash
# Run tests
uv run -m pytest tests/ -v

# Run single test
uv run -m pytest tests/test_phase2_geo_hex.py::test_name -v

# Generate map
uv run python incremental_map_builder.py
```

## Key Info

- `.hmap` files are ZIP archives containing `Descriptor.hmd` + `Save.hms`
- See `docs/HUMANKIND_MAP_FORMAT.md` for texture encoding details
- See `docs/ISSUES.md` for known rendering problems
- Config in `config.yaml` (use "new" active config)
