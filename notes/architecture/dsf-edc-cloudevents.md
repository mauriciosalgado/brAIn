# DSF EDC Cloud Events

This document describes how the EDC Connector is capable of publishing domain events as cloud events.

Tags: #edc #architecture #cloudevents #domainevents

---

## Cloud Events

CloudEvents is a specification for describing event data in common formats to provide interoperability
across services, platforms and systems.

The DSF EDC distribution loosely follows this specification when publishing domain events, so that all
mandatory fields are present but the followed structure is non-standard.

This means that no official SDKs are used, and the specific structure used to publish the events varies
with the technology used.

## Events and Event Framework

The Connector creates domain events during its activity. They occur when stateful changes are made, such
as creating entities (assets, policy definitions, ...), initiating contract negotiations, or starting a
transfer process.

The upstream Connector distribution already provides an eventing framework based on the Publish - Subscriber
pattern, so that the domain events can be handled in many ways. This framework comprises the following
components:

- `Event Envelope` - Wraps an event payload and includes metadata, such as the timestamp at which it occured.
- `Event Router` - Middleware where Event Subscribers can register themselves to receive events. It's also where events are distributed.
- `Event Subscriber` - Implementation capable of handling a published event.

There is a reference implementation upstream to publish domain events via HTTP and following the Cloud Events spec.

## Subscribers in the DSF EDC Connector

The DSF EDC distrbutions contains two Event Subscribers. One publishes the event to an SNS Topic, and
another publishes the event to a Kafka topic.

### SNS

This extension is primarily used to save the domain events as audit logs. The published event is processed
via Lambda and stored in an S3 bucket. Given the possibility to attach subscribers to the SNS topic, this
setup is extensible for further necessities with AWS infrastructure.

### Kafka

This extension is primarily used to share events via BMW infrastructure, as the Kafka topics are managed by
the Streaming Services team. Events can be consumed by authorised BMW teams, such as the DSCP team.

---

## References

- [Cloud Events offical specification](https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md)
- [HTTP reference implementation](https://github.com/eclipse-edc/Connector/tree/main/extensions/common/events/events-cloud-http)
- [DSF SNS extension](https://atc-github.azure.cloud.bmw/Extended-Enterprise-Catena-X/dsf-product-edc/tree/main/dsf-edc-extensions/common/events/events-cloud-sns)
- [DSF Kafka extension](https://atc-github.azure.cloud.bmw/Extended-Enterprise-Catena-X/dsf-product-edc/tree/main/dsf-edc-extensions/common/events/events-cloud-kafka)

---
