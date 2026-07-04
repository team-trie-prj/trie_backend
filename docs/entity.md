# Entity

---

## User

id

name

email

provider

providerId

createdAt

updatedAt

---

## RefreshToken

id

userId

token

expiredAt

---

## Document

id

filename

filePath

domain

uploadedBy

createdAt

---

## SearchSession

id

uuid

userId

query

domain

createdAt

---

## Report

id

searchSessionId

markdown

createdAt

---

## PublicDataMetadata

id

source

apiName

parameter

createdAt