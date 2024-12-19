import os
from flask import Flask, request, jsonify
import google.generativeai as genai

import requests

app = Flask(__name__)

# Configuração da chave de API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Definição das funções que o modelo pode utilizar
def get_exchange_rate(first_currency_code: str, second_currency_code: str): 
    url = f"https://economia.awesomeapi.com.br/json/last/{first_currency_code}-{second_currency_code}"
    
    response = requests.get(url)
    data = response.json()
        
    return data
    
# Declaração das funções que o modelo pode utilizar
tools = genai.protos.Tool(function_declarations=[
    genai.protos.FunctionDeclaration(
        name="get_exchange_rate",
        description="Get the exchange between two currencies. Use your knowledge of currency code to get the properties",
        parameters={
            "type": "OBJECT",
            "properties": {
                "first_currency_code": {
                    "type": "STRING",
                    "description": "Code of the first currency, e.g., BRL"
                },
                "second_currency_code": {
                    "type": "STRING",
                    "description": "Code of the second currency, e.g., EUR"
                }
            }
        },
    )
])

# Inicialização do modelo Gemini 1.5 Flash
model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"temperature": 0}, tools=[tools])

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    if not user_input:
        return jsonify({'error': 'Mensagem não fornecida'}), 400

    chat = model.start_chat()
        
    # Contrução do prompt
    prompt = "User Question: " + user_input + "\n"
    prompt += f"""
        You are Gemini, a large language model trained by Google.

        You have the tool to be used in the following circumstances:
        - User is asked to quote a currency
        - User asks the price of a coin
        For example, if user asks 'What is the Real Dollar exchange rate?' the tool params should be 'BRL' and 'USD'.
        ALWAYS refine the user question to get the most accurate results, NEVER use the user question as is.
        If you are unsatisfied with the original results retry with a better query.
        Think Step by Step: 1. Understand the user question 2. Refine the query 3. Get the search results 4. Summarize the search results in a concise manner.
    """
    
    # Envia o promp para o modelo, para conseguir a primeira resposta
    response = chat.send_message(prompt)
    response = response.candidates[0].content.parts[0]
            
    print(f"Primeira Resposta: {response}")
            
    function_calling_in_process = True
    while function_calling_in_process:
        try:
            params = {}
            # Extrai os argumentos da resposta
            for key, value in response.function_call.args.items():
                params[key] = value

            print(f"Função a ser chamada: {response.function_call.name}")
            print(f"Parametros da função: {params}")

            # Se a função a ser chamada for a "get_exchange_rate" passe o parametros para ela
            if response.function_call.name == "get_exchange_rate":
                first_currency_code = params["first_currency_code"]
                second_currency_code = params["second_currency_code"]
                api_response = get_exchange_rate(first_currency_code, second_currency_code)
               

            print(f"Resposta da Requisição (get_exchange_rate): {api_response}")

            response = chat.send_message(
                genai.protos.Content(
                    parts=[genai.protos.Part(
                        function_response = genai.protos.FunctionResponse(
                            name='get_exchange_rate',
                            response={'result': api_response}
                        )
                    )]
                )
            )

            response = response.candidates[0].content.parts[0]

        except AttributeError:
                function_calling_in_process = False
   
    return jsonify({'response': response.text})

if __name__ == '__main__':
    app.run(debug=True)
