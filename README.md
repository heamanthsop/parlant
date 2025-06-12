
<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/emcie-co/parlant/blob/develop/LogoTransparentLight.png?raw=true">
  <img alt="Parlant Banner" src="https://github.com/emcie-co/parlant/blob/develop/LogoTransparentDark.png?raw=true" width=400 />
</picture>

<a href="https://trendshift.io/repositories/12768" target="_blank"><img src="https://trendshift.io/api/badge/repositories/12768" alt="emcie-co%2Fparlant | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>



  <p>
    <a href="https://www.parlant.io/" target="_blank">Website</a> —
    <a href="https://www.parlant.io/docs/quickstart/introduction" target="_blank">Introduction</a> —
    <a href="https://www.parlant.io/docs/tutorial/getting-started" target="_blank">Tutorial</a> —
    <a href="https://www.parlant.io/docs/about" target="_blank">About</a> —
    <a href="https://www.reddit.com/r/parlant_official/" target="_blank">Reddit</a>
  </p>



  <p>
    <a href="https://pypi.org/project/parlant/" alt="Parlant on PyPi"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/parlant"></a>
    <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/parlant">
    <a href="https://opensource.org/licenses/Apache-2.0"><img alt="Apache 2 License" src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" /></a>
    <img alt="GitHub commit activity" src="https://img.shields.io/github/commit-activity/w/emcie-co/parlant?label=commits">
    <img alt="PyPI - Downloads" src="https://img.shields.io/pypi/dm/parlant">
    <a href="https://discord.gg/duxWqxKk6J"><img alt="Discord" src="https://img.shields.io/discord/1312378700993663007?style=flat&logo=discord&logoColor=white&label=discord">
</a>
  </p>

</div>

# The Conversation Modeling Engine for Great Agentic UX

[](https://pypi.org/project/parlant/)
[](https://opensource.org/licenses/MIT)
[](https://github.com/emcie-co/parlant/stargazers)
[](https://www.google.com/search?q=YOUR_DISCORD_INVITE_LINK)

## 💡 Empowering LLMs with Control and Purpose

**Parlant is an open-source conversation modeling engine that gives you unparalleled control over Large Language Models (LLMs), enabling the creation of truly deliberate, predictable, and compliant Agentic User Experiences (UX).**

Say goodbye to the unpredictability of raw LLMs. Parlant provides a structured framework to guide your generative AI conversations, ensuring agents adhere to predefined principles, actions, and objectives, leading to purposeful and reliable interactions.

**Watch our introduction video on YouTube: https://www.youtube.com/watch?v=_39ERIb0100**

## ✨ Why Parlant? Addressing Key LLM Pain Points

Traditional LLMs often struggle with **attention drift** and **inconsistency in complex conversations** when handling multiple instructions, hindering their reliability in production environments. Parlant was built to solve these critical challenges, offering a unique approach to building conversational AI:

  * **Eliminate Inconsistency:** Through **dynamic guideline matching**, Parlant ensures instructions are always contextually relevant, providing consistent and reliable LLM behavior even in intricate dialogue flows.
  * **Controlled Generative AI:** Dictate and enforce exact conversation behavior, ensuring your agents stay on topic, follow protocols, and deliver consistent responses.
  * **Compliance & Reliability:** Critical for regulated industries, Parlant helps you ensure conversations meet strict business and legal requirements by controlling and **sanitizing LLM outputs**.
  * **Purposeful Interactions:** Guide agents to achieve specific objectives, making every conversation efficient and impactful.
  * **Rapid & Iterative Development:** Quickly tailor and iteratively shape conversational agents through continuous conversation and response refinement, leveraging either a code-driven or CLI-based configuration approach.

## 🛠️ Key Features

  * **Behavioral Guidelines:** Easily define rules and guardrails for agent interactions and **dictate and enforce exact conversation behavior**.
  * **Semantic Relationships:** Define how different guidelines relate to each other (dependencies, prioritization, etc.), creating sophisticated and adaptive conversational flows.
  * **Tool Integration:** Seamlessly attach external tools (APIs, databases, etc.) with specific guidance for agent usage.
  * **Context Awareness:** Intelligently tracks conversation progress, understanding what instructions need to apply at each point, and when required actions have already been taken.
  * **Dynamic Guideline Matching:** Ensures contextually relevant instruction execution, eliminating irrelevant instructions at any point in the conversation — solving LLM attention drift.
  * **Utterance Templates:** Sanitize LLM outputs, preventing unpredictable or inaccurate messages and ensuring compliance and accuracy.
  * **Glossary Management:** Control and manage the agent's vocabulary for consistent and accurate communication.
  * **Contextual Information:** Inject customer-specific or domain-specific information for personalized and relevant responses.
  * **Continuous Re-evaluation:** The Parlant engine constantly assesses the conversational situation, checks relevant guidelines, gathers necessary information, and re-evaluates its approach.

## 🚀 Getting Started

Getting Parlant up and running is straightforward.

### Installation

```bash
pip install parlant
```

### Quick Example

Here’s a basic example to demonstrate how Parlant can be used to define a simple conversational car sales agent.

#### Demo

<img alt="Parlant Demo" src="https://github.com/emcie-co/parlant/blob/develop/demo.gif?raw=true" />

#### Code

```python
import parlant.sdk as p
import asyncio
from textwrap import dedent


@p.tool
async def get_on_sale_car(context: p.ToolContext) -> p.ToolResult:
    return p.ToolResult("Hyundai i20")


@p.tool
async def human_handoff(context: p.ToolContext) -> p.ToolResult:
    await notify_sales(context.customer_id, context.session_id)

    return p.ToolResult(
        data="Session handed off to sales team",
        # Disable auto-responding using the AI agent
        # on this session, following the next message.
        control={"mode": "manual"},
    )


async def configure_agent(server: p.Server) -> None:
    agent = await server.create_agent(
        name="Johnny",
        description="You work at a car dealership",
    )

    # Create a new supported customer journey
    journey = await agent.create_journey(
        title="Research Car",
        conditions=[
            "The customer wants to buy a new car",
            "The customer expressed general interest in new cars",
        ],
        description=dedent("""\
            Help the customer come to a decision of what new car to get.

            The process goes like this:
            1. First try to actively understand their needs
            2. Once needs are clarified, recommend relevant categories or specific models for consideration.
            3. Continue the conversation until the customer is ready to buy a car."""),
    )

    # Define guidelines specific to this journey, to handle
    # edge cases and happy-path deviations in a guided way.

    offer_on_sale_car = await journey.create_guideline(
      condition="the customer indicates they're on a budget",
      action="offer them a car that is on sale",
      tools=[get_on_sale_car],
    )

    transfer_to_sales = await journey.create_guideline(
      condition="the customer clearly stated they wish to buy a specific car",
      action="transfer them to the sales team",
      tools=[human_handoff],
    )

    # If the customer wants to buy a car, immediately transfer them
    # to a human, ignoring other guidelines which may simultaneously apply.

    await transfer_to_sales.prioritize_over(offer_on_sale_car)


async def start_conversation_server() -> None:
    async with p.Server() as server:
      await configure_agent(server)

if __name__ == "__main__":
    asyncio.run(start_conversation_server())
    # After running, visit http://localhost:8800
    # for an integrated playground web UI.
```

**For more detailed installation instructions and advanced usage, please refer to our [Official Documentation](https://parlant.io).**

## React Widget
Please see https://github.com/emcie-co/parlant-chat-react for our official, highly-customizable React widget to interact with your Parlant server on your app.

```typescript
import React from 'react';
import ParlantChatbox from 'parlant-chat-react';

function App() {
  return (
    <div>
      <h1>My Application</h1>
      <ParlantChatbox
        float
        agentId="AGENT_ID"
        server="PARLANT_SERVER_URL"
      />
    </div>
  );
}

export default App;
```


## 🌐 Use Cases & Industries

Parlant is ideal for organizations that demand precision and reliability from their AI agents. It's currently being used to deliver complex conversational agents in:

  * **Regulated Financial Services:** Ensuring compliance and accuracy in customer interactions.
  * **Healthcare Communications:** Providing accurate, compliant, and sensitive patient information.
  * **Legal Assistance:** Delivering reliable and verifiable legal guidance.
  * **Compliance-Focused Use Cases:** Automating adherence to industry standards and strict protocols.
  * **Brand-Sensitive Customer Service:** Maintaining consistent brand voice and policies across all interactions.
  * **Personal Advocacy & Representation:** Supporting structured and goal-oriented dialogues for high-stakes scenarios.

## 🤝 Contributing
We use the Linux-standard Developer Certificate of Origin (DCO.md), so that, by contributing, you confirm that you have the rights to submit your contribution under the Apache 2.0 license (i.e., that the code you're contributing is truly yours to share with the project).

Please consult [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

Can't wait to get involved? Join us on Discord and let's discuss how you can help shape Parlant. We're excited to work with contributors directly while we set up our formal processes!

## 📧 Contact & Support

Need help? Ask us anything on [Discord](https://discord.gg/duxWqxKk6J). We're happy to answer questions and help you get up and running!
