# Placing a hold on a card
Charging a card consists of three steps:

**🕵️ Authentication -** Card information is sent to the card issuer for verification. Some cards may require the cardholder to strongly authenticate the purchase through protocols like [3D Secure](https://stripe.com/ie/guides/3d-secure-2). 

**💁 Authorization -** Funds from the customer's account are put on hold but not transferred to the merchant. 

**💸 Capture -** Funds are transferred to the merchant's account and the payment is complete.

The [Payment Intents API](https://stripe.com/docs/api/payment_intents) abstracts away these three stages by handling all steps of the process through the [confirm method](https://stripe.com/docs/api/payment_intents/confirm). If you want to split the authorization + capture steps to place a hold on a customer's card and capture later after a certain event, set capture_method to manual when creating a PaymentIntent.

Note that funds must be captured within **7 days** of authorizing the card or the PaymentIntent reverts back to a status of "requires_payment_method". If you want to charge a customer more than 7 days after collecting their card details see our sample on [saving cards](https://github.com/stripe-samples/saving-card-without-payment).

**Demo**

See a [hosted version](https://nbzjj.sse.codesandbox.io/) of the demo or fork a copy on [codesandbox.io](https://codesandbox.io/s/stripe-sample-placing-a-hold-nbzjj)

The demo is running in test mode -- use `4242424242424242` as a test card number with any CVC code + a future expiration date.

Use the `4000000000003220` test card number to trigger a 3D Secure challenge flow.

Read more about testing on Stripe at https://stripe.com/docs/testing.

<img src="./placing-hold-preview.png" alt="Checkout page to place a hold" align="center">

There are two implementations depending on whether you want to use webhooks for any post-payment process: 
* **[/using-webhooks](/using-webhooks)** Confirms the payment on the client and requires using webhooks or other async event handlers for any post-payment logic (e.g. sending email receipts, fulfilling orders). 
* **[/without-webhooks](/without-webhooks)** Confirms the payment on the server and allows you to run any post-payment logic right after.

This sample shows:
<!-- prettier-ignore -->
|     | Using webhooks | Without webhooks
:--- | :---: | :---:
💳 **Collecting card and cardholder details.** Both integrations use [Stripe Elements](https://stripe.com/docs/stripe-js) to build a custom checkout form. | ✅  | ✅ |
🙅 **Handling card authentication requests and declines.** Attempts to charge a card can fail if the bank declines the purchase or requests additional authentication.  | ✅  | ✅ |
💁 **Placing a hold on a card.** By setting capture_method to "manual" when creating a PaymentIntent, you split the authorization and capture steps. | ✅ | ✅ |
↪️ **Using webhooks to respond to a hold being placed on the card.** Confirming the payment on the client requires using webhooks for any follow up actions, like capturing the funds. | ✅ | ❌ |
🏦 **Easily scalable to other payment methods.** Webhooks enable easy adoption of other asynchroneous payment methods like direct debits and push-based payment flows. | ✅ | ❌ |


## How to run locally

This sample includes 5 server implementations in Node, Ruby, Python, Java, and PHP for the two integration types: [using-webhooks](/using-webhooks) and [without-webhooks](/without-webhooks). 

Follow the steps below to run locally.

**Using the Stripe CLI**

If you haven't already installed the CLI, follow the [installation steps](https://github.com/stripe/stripe-cli#installation) in the project README. The CLI is useful for cloning samples and locally testing webhooks and Stripe integrations.

In your terminal shell, run the Stripe CLI command to clone the sample:

```
stripe samples create placing-a-hold
```

The CLI will walk you through picking your integration type, server and client languages, and configuring your .env config file with your Stripe API keys.

**Installing and cloning manually**

If you do not want to use the Stripe CLI, you can manually clone and configure the sample yourself:

**1. Clone the repository:**

```
git clone https://github.com/stripe-samples/placing-a-hold
```

**2. Copy the .env.example to a .env file:**

Copy the .env.example file into a file named .env in the folder of the server you want to use. For example:

```
cp .env.example using-webhooks/server/node/.env
```

You will need a Stripe account in order to run the demo. Once you set up your account, go to the Stripe [developer dashboard](https://stripe.com/docs/development#api-keys) to find your API keys and update your .env file with the keys.

```
STRIPE_PUBLISHABLE_KEY=<replace-with-your-publishable-key>
STRIPE_SECRET_KEY=<replace-with-your-secret-key>
```

`CLIENT_DIR` tells the server where to the client files are located and does not need to be modified unless you move the server files.

**3. Follow the server instructions on how to run:**

Pick the server language you want and follow the instructions in the server folder README on how to run.

For example, if you want to run the Node server in `using-webhooks`:

```
cd using-webhooks/server/node # there's a README in this folder with instructions
npm install
npm start
```

**4. [Optional] Run a webhook locally:**

If you want to test the `using-webhooks` integration with a local webhook on your machine, you can use the Stripe CLI to easily spin one up.

First [install the CLI](https://stripe.com/docs/stripe-cli) and [link your Stripe account](https://stripe.com/docs/stripe-cli#link-account).

```
stripe listen --forward-to localhost:4242/webhook
```

The CLI will print a webhook secret key to the console. Set `STRIPE_WEBHOOK_SECRET` to this value in your .env file.

You should see events logged in the console where the CLI is running.

When you are ready to create a live webhook endpoint, follow our guide in the docs on [configuring a webhook endpoint in the dashboard](https://stripe.com/docs/webhooks/setup#configure-webhook-settings). 


## FAQ
Q: Why did you pick these frameworks?

A: We chose the most minimal framework to convey the key Stripe calls and concepts you need to understand. These demos are meant as an educational tool that helps you roadmap how to integrate Stripe within your own system independent of the framework.

## Get support
If you found a bug or want to suggest a new [feature/use case/sample], please [file an issue](../../issues).

If you have questions, comments, or need help with code, we're here to help:
- on [IRC via freenode](https://webchat.freenode.net/?channel=#stripe)
- on Twitter at [@StripeDev](https://twitter.com/StripeDev)
- on Stack Overflow at the [stripe-payments](https://stackoverflow.com/tags/stripe-payments/info) tag
- by [email](mailto:support+github@stripe.com)

## Author(s)
[@adreyfus-stripe](https://twitter.com/adrind)
