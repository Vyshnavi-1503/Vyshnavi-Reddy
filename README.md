# EventPilot

A responsive event-planning dashboard with a built-in AI planning assistant connected to your local Ollama models.

## Run locally

1. Make sure Ollama is running and the models are installed (`ollama list`).
2. From this folder, start the site:

   ```sh
   python3 server.py
   ```

3. Open [http://localhost:8765](http://localhost:8765).

Pilot can use `qwen2.5:3b`, `llama3.2:latest`, or `qwen2.5:7b`. The model menu shows which ones are available in Ollama. The default is `qwen2.5:3b`.

Set `OLLAMA_URL` if Ollama is listening on a different address, or `PORT` to choose a different site port. For example:

```sh
OLLAMA_URL=http://localhost:11434 python3 server.py
```
