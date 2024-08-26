from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, PromptTemplate

messages=[
    HumanMessagePromptTemplate(
        prompt=PromptTemplate(
            input_variables=['context'], 
            template="""
                You are an assistant for document labeling tasks. 
                Use the following pieces of retrieved context to label the document. 
                If you don't know the answer, just say that you don't know. 
                Return your answer in JSON with the format:

                {{
                    "company": "<company name>", 
                    "label": "<audited financial statement or not>"
                    "year": "<financial statement year>",
                }}
                
                Don't return anything else, just respond with your JSON.
                
                \nContext: {context} 
                \nAnswer:
                """
                )
        )
    ]

chat_prompt = ChatPromptTemplate.from_messages(messages)