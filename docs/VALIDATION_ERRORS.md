# Humankind Map Validation Errors Reference

Extracted from game screenshots taken 2026-01-10.

## Validation Categories

The Humankind map editor validates maps in these categories:
- Entity - Validate
- Territory - Validate
- Natural Wonder - Validate
- Tile - Validate
- DLC - Validate
- Multi Passes: All - Validate, Mandatory - Validate

## Known Validation Errors

### Not Contiguous Territory (Territory Category)

**Error Message**: "Edge of the world Territory not contiguous"

**Advice**: "The edge of the world territory tiles must be contiguous with one another or touch the edge of the world"

**Count in test map**: 11 errors

**Root Cause**: Territory 0 (the "edge of world" or ocean territory) contains tiles that are not connected to each other or to the map boundary. All tiles assigned to territory 0 should either:
1. Be physically connected to other territory 0 tiles (share an edge)
2. Touch the edge of the map (be on row 0, row max, col 0, or col max)

**Fix Strategy**:
- Ensure territory 0 tiles form a contiguous region
- Or assign isolated ocean/water tiles to adjacent land territories
- Or ensure each territory 0 tile touches the map boundary

## Validation Implementation Notes

To implement territory contiguity checking:
1. Extract the ZonesTexture from the hmap file
2. The B channel of ZonesTexture contains territory assignments
3. Group all pixels by territory ID
4. For each territory, verify all tiles form a connected region using flood-fill
5. For territory 0 specifically, verify tiles touch map edges or connect to other territory 0 tiles
