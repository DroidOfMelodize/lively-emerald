// Lively Emerald: helpers for Pokémon placed on maps as simple object events.
#include "global.h"
#include "event_data.h"
#include "event_object_movement.h"
#include "pokemon.h"
#include "string_util.h"
#include "constants/event_objects.h"
#include "constants/species.h"

// Older, fixed Pokémon sprites from vanilla Emerald that don't carry a species.
static const struct { u16 graphicsId; u16 species; } sLegacyMonGraphics[] =
{
    { OBJ_EVENT_GFX_ZIGZAGOON_1, SPECIES_ZIGZAGOON },
    { OBJ_EVENT_GFX_ZIGZAGOON_2, SPECIES_ZIGZAGOON },
    { OBJ_EVENT_GFX_POOCHYENA,   SPECIES_POOCHYENA },
    { OBJ_EVENT_GFX_WINGULL,     SPECIES_WINGULL },
    { OBJ_EVENT_GFX_SKITTY,      SPECIES_SKITTY },
    { OBJ_EVENT_GFX_AZURILL,     SPECIES_AZURILL },
    { OBJ_EVENT_GFX_AZUMARILL,   SPECIES_AZUMARILL },
    { OBJ_EVENT_GFX_KECLEON,     SPECIES_KECLEON },
    { OBJ_EVENT_GFX_KIRLIA,      SPECIES_KIRLIA },
    { OBJ_EVENT_GFX_DUSCLOPS,    SPECIES_DUSCLOPS },
    { OBJ_EVENT_GFX_PIKACHU,     SPECIES_PIKACHU },
    { OBJ_EVENT_GFX_SUDOWOODO,   SPECIES_SUDOWOODO },
};

static u16 GetObjectEventSpecies(const struct ObjectEvent *objectEvent)
{
    u32 i;

    if (IS_OW_MON_OBJ(objectEvent))
        return OW_SPECIES(objectEvent);

    for (i = 0; i < ARRAY_COUNT(sLegacyMonGraphics); i++)
    {
        if (sLegacyMonGraphics[i].graphicsId == objectEvent->graphicsId)
            return sLegacyMonGraphics[i].species;
    }
    return SPECIES_NONE;
}

// special BufferTalkedPokemonSpecies
// Sets VAR_RESULT to the species of the object the player just talked to
// (SPECIES_NONE if it isn't a Pokémon) and copies its name into STR_VAR_1.
void BufferTalkedPokemonSpecies(void)
{
    u16 species = GetObjectEventSpecies(&gObjectEvents[gSelectedObjectEvent]);

    gSpecialVar_Result = species;
    if (species != SPECIES_NONE)
        StringCopy(gStringVar1, GetSpeciesName(species));
}
