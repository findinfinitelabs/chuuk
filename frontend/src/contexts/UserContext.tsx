import { createContext, useContext } from 'react'

interface UserContextType {
  email: string | null
  name: string | null
  role: string | null
}

export const UserContext = createContext<UserContextType>({
  email: null,
  name: null,
  role: null
})

export function useUser() {
  return useContext(UserContext)
}
