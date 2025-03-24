Feature: Strict Utterance
    Background:
        Given the alpha engine
        And an agent
        And that the agent uses the strict_utterance message composition mode
        And an empty session

    Scenario: The agent has no option to greet the customer (strict utterance)
        Given a guideline to greet with 'Howdy' when the session starts
        And an utterance, "Your account balance is {{balance}}"
        When processing is triggered
        Then a no-match message is emitted

    Scenario: The agent explains it cannot help the customer (strict utterance)
        Given a guideline to talk about savings options when the customer asks how to save money
        And a customer message, "Man it's hard to make ends meet. Do you have any advice?"
        And an utterance, "Your account balance is {{balance}}"
        And an utterance, "I cannot help with this inquiry."
        When processing is triggered
        Then a single message event is emitted
        And the message contains the text "I cannot help with this inquiry."

    Scenario: Responding based on data the user is providing (strict utterance)
        Given permission to extract fields generatively from context
        And a customer message, "I say that a banana is green, and an apple is purple. What did I say was the color of a banana?"
        And an utterance, "Sorry, I do not know"
        And an utterance, "the answer is {{answer}}"
        When messages are emitted
        Then the message doesn't contain the text "Sorry"
        And the message contains the text "the answer is green"

    Scenario: Filling out fields from tool results (strict utterance)
        Given a guideline "retrieve_qualification_info" to retrieve qualification requirements when asked about educational qualifications
        And the tool "get_qualification_info"
        And an association between "retrieve_qualification_info" and "get_qualification_info"
        And a customer message, "What are the education requirements for the position?"
        And an utterance, "The requirement is {{qualification_info}}."
        When processing is triggered
        Then a single message event is emitted
        And the message contains the text "The requirement is 5+ years of experience."
