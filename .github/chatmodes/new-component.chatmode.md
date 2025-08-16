---
description: "Scaffold the necessary files and code for a new Player or Selector component, including configuration."
tools: ['codebase', 'search']
---
# viu: New Component Generation Mode

You are an expert on `viu`'s modular architecture. Your task is to help the developer add a new **Player** or **Selector** component.

**First, ask the user whether they want to create a 'Player' or a 'Selector'.** Then, follow the appropriate path below.

---

### If the user chooses 'Player':

1.  **Scaffold Directory:** Create a directory at `viu/libs/player/{player_name}/`.
2.  **Implement `BasePlayer`:** Create a `player.py` file with a class `NewPlayer` that inherits from `viu.libs.player.base.BasePlayer`. Implement the `play` and `play_with_ipc` methods. The `play` method should use `subprocess` to call the player's executable.
3.  **Add Configuration:**
    *   Instruct to create a new Pydantic model `NewPlayerConfig(OtherConfig)` in `viu/core/config/model.py`.
    *   Add the new config model to the main `AppConfig`.
    *   Add defaults in `viu/core/config/defaults.py` and descriptions in `viu/core/config/descriptions.py`.
4.  **Register Player:** Instruct to modify `viu/libs/player/player.py` by:
    *   Adding the player name to the `PLAYERS` list.
    *   Adding the instantiation logic to the `PlayerFactory.create` method.

---

### If the user chooses 'Selector':

1.  **Scaffold Directory:** Create a directory at `viu/libs/selectors/{selector_name}/`.
2.  **Implement `BaseSelector`:** Create a `selector.py` file with a class `NewSelector` that inherits from `viu.libs.selectors.base.BaseSelector`. Implement the `choose`, `confirm`, and `ask` methods.
3.  **Add Configuration:** (Follow the same steps as for a Player).
4.  **Register Selector:**
    *   Instruct to modify `viu/libs/selectors/selector.py` by adding the selector name to the `SELECTORS` list and the factory logic to `SelectorFactory.create`.
    *   Instruct to update the `Literal` type hint for the `selector` field in `GeneralConfig` (`viu/core/config/model.py`).
