#!/usr/bin/env python3
"""Remove ExampleDS from RHSSO standalone-openshift.xml before WildFly processes it."""
import re

CONFIG = "/opt/eap/standalone/configuration/standalone-openshift.xml"

with open(CONFIG, "r") as f:
    content = f.read()

count_before = content.count("ExampleDS")

# Remove entire ExampleDS datasource block
content = re.sub(
    r'\s*<datasource[^>]*jndi-name[^>]*ExampleDS.*?</datasource>',
    '',
    content,
    flags=re.DOTALL
)
# Remove any remaining ExampleDS references
content = re.sub(r'\s*<datasource-ref>ExampleDS</datasource-ref>', '', content)

count_after = content.count("ExampleDS")

with open(CONFIG, "w") as f:
    f.write(content)

print(f"ExampleDS occurrences: {count_before} -> {count_after}")
print("Done — ExampleDS removed from RHSSO standalone-openshift.xml")
