Feature: Fluid Utterance
    Background:
        Given the alpha engine
        And an agent
        And that the agent uses the fluid_utterance message composition mode
        And an empty session

    Scenario: Multistep journey is aborted when the journey description requires so (fluid utterance)
        Given a journey titled Reset Password Journey to follow these steps to reset a customers password: 1. ask for their account name 2. ask for their email or phone number 3. Wish them a good day and only proceed if they wish one back to you. Otherwise let them know that the password could not be reset. 4. use the tool reset_password with the provided information 5. report the result to the customer when the customer wants to reset their password
        And an utterance, "What is the name of your account?"
        And an utterance, "can you please provide the email address or phone number attached to this account?"
        And an utterance, "Your password was successfully reset. An email with further instructions will be sent to your address."
        And an utterance, "Your password could not be reset at this time. Please try again later."
        And the tool "reset_password"
        And a customer message, "I want to reset my password"
        And an agent message, "I can help you do just that. What's your username?"
        And a customer message, "it's leonardo_barbosa_1982"
        And an agent message, "Great! And what's the account's associated email address or phone number?"
        And a customer message, "the email is leonardobarbosa@gmail.br"
        And an agent message, "Got it. Before proceeding to reset your password, I wanted to wish you a good day"
        And a customer message, "What? Just reset my password please"
        When processing is triggered
        When processing is triggered
        Then no tool calls event is emitted
        And a single message event is emitted
        And the message contains either that the password could not be reset at this time

    Scenario: Simple journey is followed to inform decision (fluid utterance)
        Given a guideline "recommend_pizza" to recommend either tomato, mushrooms or pepperoni when the customer asks for topping recommendations
        And an utterance, "I recommend tomatoes"
        And an utterance, "I recommend tomatoes or mushrooms"
        And an utterance, "I recommend tomatoes, mushrooms or pepperoni"
        And an utterance, "I recommend tomatoes or pepperoni"
        And an utterance, "I recommend mushrooms"
        And an utterance, "I recommend mushrooms or pepperoni"
        And an utterance, "I recommend pepperoni"
        And a journey titled Vegetarian Customers to Be aware that the customer is vegetarian. Only discuss vegetarian options with them. when the customer has a name that begins with R
        And a customer message, "Hey, there. How are you?"
        And an agent message, "I'm doing alright, thank you! What's your name?"
        And a customer message, "Rajon, have we spoken before? I want one large pie but I'm not sure which topping to get, what do you recommend?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains recommendations for either mushrooms or tomatoes, but not pepperoni

    Scenario: Multistep journey invokes tool calls correctly (fluid utterance)
        Given a journey titled Reset Password Journey to follow these steps to reset a customers password: 1. ask for their account name 2. ask for their email or phone number 3. Wish them a good day and only proceed if they wish one back to you. Otherwise abort. 3. use the tool reset_password with the provided information 4. report the result to the customer when the customer wants to reset their password
        And the tool "reset_password"
        And a guideline "reset_password_guideline" to reset the customer's password using the associated tool when the customer requested to reset their password
        And an association between "reset_password_guideline" and "reset_password"
        And a customer message, "I want to reset my password"
        And an agent message, "I can help you do just that. What's your username?"
        And a customer message, "it's leonardo_barbosa_1982"
        And an agent message, "Great! And what's the account's associated email address or phone number?"
        And a customer message, "the email is leonardobarbosa@gmail.br"
        And an agent message, "Got it. Before proceeding to reset your password, I wanted to wish you a good day"
        And a customer message, "Thank you! Have a great day as well!"
        And an utterance, "What is the name of your account?"
        And an utterance, "can you please provide the email address or phone number attached to this account?"
        And an utterance, "Thank you, have a good day!"
        And an utterance, "I'm sorry but I have no information about that"
        And an utterance, "Is there anything else I could help you with?"
        And an utterance, "Your password was successfully reset. An email with further instructions will be sent to your address."
        And an utterance, "An error occurred, your password could not be reset"
        When processing is triggered
        Then a single tool calls event is emitted
        And the tool calls event contains 1 tool call(s)
        And the tool calls event contains the tool reset password with username leonardo_barbosa_1982 and email leonardobarbosa@gmail.br 
        And a single message event is emitted
        And the message contains that the password was reset and an email with instructions was sent to the customer
