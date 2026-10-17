@ Lively Emerald: generic script for Pokémon standing around on a map.
@ Set an object's script to EventScript_TalkToPokemon in porymap. Talking to it
@ turns it towards the player, plays its cry and shows its name.
@ Works with OBJ_EVENT_GFX_SPECIES(...) sprites and the old fixed Pokémon sprites.
EventScript_TalkToPokemon::
	lock
	faceplayer
	special BufferTalkedPokemonSpecies
	goto_if_eq VAR_RESULT, SPECIES_NONE, EventScript_TalkToPokemon_End
	playmoncry VAR_RESULT, CRY_MODE_NORMAL
	msgbox Text_TalkToPokemon_Name, MSGBOX_DEFAULT
	waitmoncry
EventScript_TalkToPokemon_End:
	release
	end

Text_TalkToPokemon_Name:
	.string "{STR_VAR_1}$"
